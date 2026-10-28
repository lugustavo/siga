"""Telegram: alertas, fotos e pedido de texto (PIN) ao utilizador."""
import html
import logging
import os
import time

import requests

log = logging.getLogger("siga")


def _cfg():
    return os.environ.get("BOT_TOKEN"), os.environ.get("BOT_CHAT_ID")


def enabled():
    return all(_cfg())


def esc(text):
    """Escapa texto variavel para parse_mode=HTML."""
    return html.escape(str(text), quote=False)


def send(text, photo=None):
    """Envia texto HTML (e foto opcional). Nunca levanta excecao; devolve True se enviou."""
    token, chat = _cfg()
    log.info("TELEGRAM: %s", text.replace("\n", " | ")[:300])
    if not (token and chat):
        return False
    try:
        base = f"https://api.telegram.org/bot{token}"
        if photo:
            with open(photo, "rb") as fh:
                r = requests.post(f"{base}/sendPhoto", timeout=60,
                                  data={"chat_id": chat, "caption": text[:1000], "parse_mode": "HTML"},
                                  files={"photo": fh})
        else:
            r = requests.post(f"{base}/sendMessage", timeout=30,
                              data={"chat_id": chat, "text": text[:4000], "parse_mode": "HTML"})
        if not r.ok:
            log.warning("Telegram respondeu %s: %s", r.status_code, r.text[:200])
        return r.ok
    except Exception as exc:  # o token vai no URL: nao registar a excecao completa
        log.warning("Falha ao enviar para o Telegram (%s)", type(exc).__name__)
        return False


def ask_text(prompt, timeout=300):
    """Envia 'prompt' e devolve a primeira mensagem de texto que o utilizador responder
    no chat; None se esgotar o tempo."""
    token, chat = _cfg()
    if not (token and chat):
        return None
    base = f"https://api.telegram.org/bot{token}"
    try:
        r = requests.get(f"{base}/getUpdates", params={"timeout": 0}, timeout=30).json()
        offset = (r["result"][-1]["update_id"] + 1) if r.get("result") else 0
        send(prompt)
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = requests.get(f"{base}/getUpdates", timeout=40,
                             params={"offset": offset, "timeout": min(25, max(1, int(deadline - time.time())))}).json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or u.get("channel_post") or {}
                if str(msg.get("chat", {}).get("id")) == str(chat) and msg.get("text"):
                    return msg["text"].strip()
    except Exception as exc:
        log.warning("Falha ao pedir texto pelo Telegram (%s)", type(exc).__name__)
    return None
