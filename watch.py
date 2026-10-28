"""
Processo principal: de 'frequency' em 'frequency' minutos corre cada pesquisa de
search_config.yaml. Sem auto_book, avisa por Telegram quando ha horarios que cumprem os
filtros. Com auto_book, marca sozinho (ver DRY_RUN em bot.py).
Estado em data/state.json: depois de uma marcacao, nenhuma outra e feita (STOP_AFTER_BOOKING).
"""
import json
import logging
import os
import random
import time
from datetime import datetime

from dotenv import load_dotenv

import bot
import config
import notify

log = logging.getLogger("siga")
STATE = bot.DATA_DIR / "state.json"


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"booked": False, "searches": {}}


def save_state(state):
    bot.DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1))


def in_hours(search, now):
    return search.start_time <= now.strftime("%H:%M") <= search.end_time


def format_slots(search, slots):
    lines = [f"<b>{notify.esc(search.title)}</b>"]
    by_local = {}
    for s in slots:
        by_local.setdefault(s.local, []).append(s.when.strftime("%d-%m-%Y %H:%M"))
    for local, whens in by_local.items():
        lines.append(f"\n<b>{notify.esc(local)}</b>")
        lines.extend(whens)
    return "\n".join(lines)


def tick(search, state, cfg):
    """Uma pesquisa. Atualiza 'state' e avisa por Telegram."""
    st = state["searches"].setdefault(search.title, {"attempts": 0, "notified": None, "gave_up": False})
    can_book = (search.auto_book and not st["gave_up"]
                and not (cfg["stop_after_booking"] and state["booked"]))
    dados = config.load_dados(bot.CONFIG_DIR / "dados.json") if can_book and cfg["dry_run"] != 1 else None
    try:
        out = bot.run(search, dados if can_book else None, cfg["dry_run"] if can_book else 1,
                      cfg["captcha_wait_s"], cfg["pin_timeout"])
    except bot.SlotUnavailable as exc:
        log.info("[%s] horario desapareceu antes de marcar (%s)", search.title, exc)
        return
    except Exception:
        if can_book and cfg["dry_run"] != 1:
            st["attempts"] += 1
            log.exception("[%s] tentativa de marcacao %d falhou", search.title, st["attempts"])
            if st["attempts"] >= cfg["max_attempts"]:
                st["gave_up"] = True
                notify.send(f"<b>{notify.esc(search.title)}</b>: {st['attempts']} falhas seguidas; "
                            "auto_book desligado ate apagar data/state.json (continua a avisar de horarios).")
        else:
            log.exception("[%s] verificacao falhou", search.title)
        return

    if out.status == "booked":
        state["booked"] = True
        log.info("[%s] marcado: %s", search.title, out.chosen.label())
        return
    if out.status == "no_slots":
        log.info("[%s] sem horarios que cumpram os filtros (%d na pagina)", search.title, len(out.all_slots))
        st["notified"] = None
        return
    key = "|".join(s.key for s in out.wanted)
    if st["notified"] != key:  # nao repetir o mesmo aviso a cada verificacao
        st["notified"] = key
        log.info("[%s] %d horario(s): %s", search.title, len(out.wanted), [s.label() for s in out.wanted])
        notify.send("<b>Horarios disponiveis</b>\n" + format_slots(search, out.wanted))


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = {
        "dry_run": int(os.environ.get("DRY_RUN", "1")),
        "max_attempts": int(os.environ.get("MAX_ATTEMPTS", "3")),
        "captcha_wait_s": int(os.environ.get("CAPTCHA_WAIT_S", "300")),
        "pin_timeout": int(os.environ.get("PIN_TIMEOUT_S", "240")),
        "stop_after_booking": os.environ.get("STOP_AFTER_BOOKING", "1") == "1",
    }
    searches, errors = config.load_searches("search_config.yaml")
    for e in errors:
        log.error("configuracao invalida: %s", e)
    if not searches:
        raise SystemExit("Nao ha pesquisas validas em search_config.yaml")
    if any(s.auto_book for s in searches):
        if cfg["dry_run"] != 1:
            config.load_dados(bot.CONFIG_DIR / "dados.json")  # falha logo no arranque se estiver mal
        log.info("auto_book ativo em %s com DRY_RUN=%s", [s.title for s in searches if s.auto_book], cfg["dry_run"])
    log.info("Telegram %s", "ativo" if notify.enabled() else "NAO configurado (so logs)")
    due = {s.title: 0.0 for s in searches}
    while True:
        now = datetime.now()
        for s in searches:
            if time.time() < due[s.title]:
                continue
            due[s.title] = time.time() + s.frequency * 60 + random.randint(0, 30)
            if not in_hours(s, now):
                log.info("[%s] fora do horario (%s-%s)", s.title, s.start_time, s.end_time)
                continue
            state = load_state()
            try:
                tick(s, state, cfg)
            except Exception:
                log.exception("[%s] tick falhou", s.title)
            save_state(state)
        time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Interrompido")
