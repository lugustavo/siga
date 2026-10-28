"""
Fluxo de marcacao no SIGA (https://siga.marcacaodeatendimento.pt) via Playwright:
  Entidade -> Assunto -> Opcoes de atendimento -> Local -> Horarios
  -> Marcar -> formulario -> reCAPTCHA -> PIN (email) -> confirmacao.

Niveis de DRY_RUN (so se aplicam a pesquisas com auto_book):
  1  le os horarios e PARA antes de clicar em Marcar          (por omissao)
  2  clica em Marcar e preenche o formulario, sem CAPTCHA/submissao
  0  marca a serio

Uso manual:
  python bot.py                      # 1.a pesquisa, DRY_RUN do .env
  python bot.py --search "CC Sintra" --dry-run 2 --auto-book   # --auto-book: so nesta execucao
"""
import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

import config
import notify
import pin as pinmod
import slots as slotmod

log = logging.getLogger("siga")

BASE = "https://siga.marcacaodeatendimento.pt"
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "config"))
SHOTS = DATA_DIR / "shots"
STEP_TIMEOUT = 45_000
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/140.0 Safari/537.36")


class SlotUnavailable(Exception):
    """O horario escolhido desapareceu entre a leitura e o clique."""


class CaptchaTimeout(Exception):
    """O reCAPTCHA nao foi resolvido a tempo."""


class PinRejected(Exception):
    """O SIGA nao aceitou o codigo de validacao."""


@dataclass
class Outcome:
    status: str                 # no_slots | slots | form_filled | booked
    all_slots: list = field(default_factory=list)
    wanted: list = field(default_factory=list)
    chosen: object = None
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------- utilitarios

def shot(page, name):
    """Captura de ecra + HTML da pagina para depurar (contem dados pessoais: ver README)."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    base = SHOTS / f"{datetime.now():%Y%m%d-%H%M%S}-{name}"
    try:
        page.screenshot(path=f"{base}.png", full_page=True)
        Path(f"{base}.html").write_text(page.content(), encoding="utf-8")
    except Exception as exc:
        log.warning("captura de ecra falhou (%s)", type(exc).__name__)
        return None
    return f"{base}.png"


def wait_idle(page, timeout=20_000):
    """O SIGA mostra #divAguarde enquanto faz pedidos ajax."""
    try:
        page.locator("#divAguarde").wait_for(state="hidden", timeout=timeout)
    except PWTimeout:
        pass
    page.wait_for_timeout(300)


def is_id(value):
    return isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit())


def select_option(page, selector, wanted):
    """Escolhe uma opcao de <select> pelo id (numero) ou pelo texto (sem acentos/maiusculas)."""
    # ha listas sem opcao "Selecione..." (ex.: um unico local de atendimento): basta uma opcao com valor
    page.wait_for_function("sel => document.querySelector(sel) && "
                           "[...document.querySelector(sel).options].some(o => o.value !== '')",
                           arg=selector, timeout=STEP_TIMEOUT)
    opts = [(o.get_attribute("value"), o.inner_text().strip()) for o in page.locator(f"{selector} option").all()]
    if is_id(wanted):
        match = [v for v, _ in opts if v == str(wanted).strip()]
    else:
        w = slotmod.norm(wanted)
        match = [v for v, t in opts if v and slotmod.norm(t) == w] or \
                [v for v, t in opts if v and w in slotmod.norm(t)]
    if not match:
        raise LookupError(f"opcao {wanted!r} nao existe em {selector}: {[t for _, t in opts if t][:25]}")
    page.select_option(selector, match[0])
    wait_idle(page)
    return next(t for v, t in opts if v == match[0])


def type_into(page, selector, value):
    el = page.locator(selector)
    el.click()
    el.fill("")
    el.press_sequentially(value, delay=25)  # dispara o oninput que valida o campo
    el.blur()


# ---------------------------------------------------------------- passos ate aos horarios

def step_inicio(page):
    page.goto(f"{BASE}/Marcacao/MarcacaoInicio", wait_until="domcontentloaded", timeout=60_000)
    page.locator("input[onclick*='Entidades']").first.click()
    page.wait_for_url(re.compile(r"/Marcacao/Entidades"), timeout=STEP_TIMEOUT)


def step_entidade(page, entity):
    btns = page.locator("button.btn-selecionar-entidade")
    btns.first.wait_for(timeout=STEP_TIMEOUT)
    for b in btns.all():
        if (is_id(entity) and b.get_attribute("id") == str(entity).strip()) or \
           (not is_id(entity) and slotmod.norm(b.get_attribute("title")) == slotmod.norm(entity)):
            label = b.get_attribute("title")
            b.click()
            page.wait_for_url(re.compile(r"/Marcacao/Assunto"), timeout=STEP_TIMEOUT)
            return label
    raise LookupError(f"entidade {entity!r} nao encontrada: "
                      f"{[b.get_attribute('title') for b in btns.all()]}")


def step_assunto(page, s):
    labels = {
        "tema": select_option(page, "#IdCategoria", s.tema),
        "subtema": select_option(page, "#IdSubcategoria", s.subtema),
        "motivo": select_option(page, "#IdMotivo", s.motivo),
    }
    num = page.locator("#NumCasos")
    if num.evaluate("e => e.tagName") == "SELECT":
        num.select_option(str(s.qtd_casos))
    else:
        num.fill(str(s.qtd_casos))
    page.click("#btnOpcoesAtendimento")
    presencial = page.locator("button[onclick='presencialSelecionarLocalAtendimento()']")
    presencial.first.wait_for(state="visible", timeout=STEP_TIMEOUT)
    page.wait_for_timeout(500)
    presencial.first.click()
    page.wait_for_url(re.compile(r"/Marcacao/Local"), timeout=STEP_TIMEOUT)
    return labels


def step_local(page, s):
    labels = {
        "distrito": select_option(page, "#IdDistrito", s.distrito),
        "localidade": select_option(page, "#IdLocalidade", s.localidade),
    }
    if s.local_atendimento:
        labels["local"] = select_option(page, "#IdLocalAtendimento", s.local_atendimento)
    page.locator("li#liProximoButton a.set-date-button").click()
    page.wait_for_url(re.compile(r"/Marcacao/HorarioLocal"), timeout=STEP_TIMEOUT)
    return labels


def read_slots(page):
    """[(Slot, botao 'Marcar')] da pagina de horarios; vazio se o SIGA nao tem sugestoes."""
    try:
        page.wait_for_selector("div.schedule-list .set-appointment, div.error-message h5",
                               state="visible", timeout=STEP_TIMEOUT)
    except PWTimeout:
        return []
    out = []
    for card in page.locator("div.schedule-list div[class^='col-md-5']").all():
        btn = card.locator(".set-appointment")
        if not btn.count():
            continue
        sl = slotmod.parse_onclick(btn.first.get_attribute("onclick"), card.get_attribute("title") or "")
        if sl:
            out.append((sl, btn.first))
    if not out:
        err = page.locator("div.error-message h5")
        if err.count():
            log.info("SIGA: %s", err.first.inner_text().strip())
    return out


# ---------------------------------------------------------------- marcacao

def step_formulario(page, dados):
    try:
        page.locator("#ModalDadosCliente").wait_for(state="visible", timeout=15_000)
    except PWTimeout:
        raise SlotUnavailable("o popup do formulario nao abriu depois de clicar em Marcar")
    type_into(page, "#NomeCliente", dados["nome"])
    page.select_option("#TipoIdentificacao", dados["tipo_identificacao"])
    type_into(page, "#NumeroIdentificacao", dados["numero"])
    if dados["email"]:
        type_into(page, "#EmailCliente", dados["email"])
    if dados["telemovel"]:
        type_into(page, "#TelemovelCliente", dados["telemovel"])
    if dados["telefone"]:
        type_into(page, "#TelefoneCliente", dados["telefone"])


def _captcha_token(page):
    try:
        return page.evaluate("(document.getElementById('g-recaptcha-response')||{}).value || ''")
    except Exception:  # a pagina pode estar a navegar depois do callback
        return ""


def _captcha_challenge_open(page):
    """True se o desafio de imagens do reCAPTCHA estiver visivel."""
    try:
        return page.evaluate("""() => {
            const f = document.querySelector("iframe[src*='recaptcha/api2/bframe']");
            if (!f) return false;
            for (let e = f.parentElement; e && e !== document.body; e = e.parentElement)
                if (getComputedStyle(e).visibility === 'hidden') return false;
            const r = f.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.top >= 0;
        }""")
    except Exception:
        return False


def _pin_modal_open(page):
    """Popup 'Codigo de validacao' (#ModalCodigo), aberto pelo servidor depois do CAPTCHA."""
    try:
        return page.locator("#ModalCodigo").is_visible()
    except Exception:  # a pagina pode estar a navegar
        return False


def step_captcha(page, wait_s, label):
    """Clica no checkbox. Se o Google pedir o desafio de imagens, avisa por Telegram e espera
    que o utilizador o resolva (noVNC). Ao resolver, o proprio site submete o formulario."""
    page.locator("#recapcha").wait_for(state="visible", timeout=STEP_TIMEOUT)  # aparece com o formulario valido
    page.frame_locator("#recapcha iframe[title='reCAPTCHA']").locator("#recaptcha-anchor").click()
    deadline = time.time() + wait_s
    warned = False
    while time.time() < deadline:
        if _captcha_token(page) or _pin_modal_open(page):
            return "automatico" if not warned else "manual"
        if _captcha_challenge_open(page) and not warned:
            warned = True
            url = os.environ.get("NOVNC_URL", "")
            log.warning("reCAPTCHA pediu desafio de imagens")
            notify.send("<b>CAPTCHA SIGA: precisa de ti</b>\n"
                        f"{notify.esc(label)}\n"
                        + (f"Resolve o desafio aqui: {notify.esc(url)}" if url else
                           "NOVNC_URL nao configurado: nao ha como resolver o desafio.")
                        + f"\nTens {wait_s // 60} min.", shot(page, "captcha"))
        page.wait_for_timeout(1000)
    raise CaptchaTimeout(f"reCAPTCHA nao resolvido em {wait_s}s")


def step_pin(page, since, pin_timeout):
    modal = page.locator("#ModalCodigo")
    try:
        modal.wait_for(state="visible", timeout=STEP_TIMEOUT)
    except PWTimeout:
        raise RuntimeError(f"popup do codigo de validacao nao apareceu: {_visible_errors(page)}")
    log.info("Popup de validacao aberto; a procurar o PIN no email")
    code = pinmod.get_pin(since, pin_timeout)
    if not code:
        raise RuntimeError("PIN nao obtido")
    box = modal.locator("input[type='text'], input:not([type]), input[type='number'], input[type='tel']").first
    box.click()
    box.fill(code)
    page.click("#btn_confirmToken")
    deadline = time.time() + STEP_TIMEOUT / 1000
    while time.time() < deadline:
        if page.get_by_text("Detalhes da marcação").count():
            return
        err = page.locator("#lbl_erro_codigo")
        if err.count() and err.first.inner_text().strip():
            raise PinRejected(err.first.inner_text().strip())
        page.wait_for_timeout(500)
    raise PinRejected(f"pagina de confirmacao nao abriu: {_visible_errors(page)}")


def _visible_errors(page):
    try:
        return [t.strip() for t in page.locator(
            ".text-danger:visible, .alert:visible, #Modal_Erro:visible"
        ).all_inner_texts() if t.strip()][:5]
    except Exception:
        return []


def read_confirmation(page):
    text = page.locator("body").inner_text()
    section = text[text.find("Detalhes da marcação"):][:900]
    code = re.search(r"C[oó]digo de Marca[cç][aã]o:\s*([A-Z0-9]+)", section)
    head = re.search(r"\d{2}-\d{2}-\d{4} - .+? - \d{2}:\d{2} - \d{2}:\d{2}", section)
    return {"codigo": code.group(1) if code else None,
            "resumo": head.group(0) if head else None,
            "texto": re.sub(r"\n{2,}", "\n", section)}


# ---------------------------------------------------------------- orquestracao

def run(search, dados=None, dry_run=1, captcha_wait_s=300, pin_timeout=240, headless=None):
    """Percorre o SIGA para 'search'. Devolve Outcome; levanta excecao se um passo falhar."""
    if headless is None:
        headless = not os.environ.get("DISPLAY") or os.environ.get("HEADLESS") == "1"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=["--no-sandbox"])
        ctx = browser.new_context(locale="pt-PT", timezone_id="Europe/Lisbon", user_agent=UA,
                                  viewport={"width": 1280, "height": 1000})
        ctx.set_default_timeout(STEP_TIMEOUT)
        page = ctx.new_page()
        chosen = None
        try:
            step_inicio(page)
            entity = step_entidade(page, search.entity)
            labels = {"entidade": entity, **step_assunto(page, search)}
            labels.update(step_local(page, search))
            pairs = read_slots(page)
            found = [p[0] for p in pairs]
            wanted = slotmod.filter_slots(found, search.max_days, search.slot_start, search.slot_end)
            if not wanted:
                return Outcome("no_slots", found, [], details=labels)
            if not search.auto_book or dry_run == 1:
                return Outcome("slots", found, wanted, details=labels)

            chosen = slotmod.pick(wanted, search.urgency)
            button = next(b for s, b in pairs if s == chosen)
            log.info("A marcar %s", chosen.label())
            button.click()
            step_formulario(page, dados)
            if dry_run == 2:
                notify.send(f"<b>Ensaio ok</b>: {notify.esc(chosen.label())}\n"
                            "Formulario preenchido; sem CAPTCHA nem submissao (DRY_RUN=2).",
                            shot(page, "formulario"))
                return Outcome("form_filled", found, wanted, chosen, labels)

            since = datetime.now(timezone.utc)
            how = step_captcha(page, captcha_wait_s, chosen.label())
            log.info("reCAPTCHA resolvido (%s)", how)
            step_pin(page, since, pin_timeout)
            info = read_confirmation(page)
            img = shot(page, "confirmacao")
            notify.send("<b>Marcacao confirmada</b>\n" + notify.esc(info["texto"]), img)
            return Outcome("booked", found, wanted, chosen, {**labels, **info})
        except Exception:
            if chosen:
                notify.send(f"<b>Falha na marcacao</b> ({notify.esc(chosen.label())})\npasso em {notify.esc(page.url)}",
                            shot(page, "erro"))
            else:
                shot(page, "erro")
            raise
        finally:
            browser.close()


def main():
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", help="titulo (ou numero, a partir de 1) da pesquisa; por omissao a primeira")
    ap.add_argument("--dry-run", type=int, choices=(0, 1, 2), default=int(os.environ.get("DRY_RUN", "1")))
    ap.add_argument("--config", default="search_config.yaml")
    ap.add_argument("--auto-book", action="store_true",
                    help="trata a pesquisa como auto_book: true so nesta execucao (sem editar o yaml)")
    a = ap.parse_args()
    searches, errors = config.load_searches(a.config)
    for e in errors:
        log.error("configuracao invalida: %s", e)
    if not searches:
        sys.exit("sem pesquisas validas")
    chosen = next((s for i, s in enumerate(searches, 1) if a.search in (s.title, str(i))), None) \
        if a.search else searches[0]
    if not chosen:
        sys.exit(f"pesquisa {a.search!r} nao existe: {[s.title for s in searches]}")
    if a.auto_book:
        chosen.auto_book = True
    if a.dry_run != 1 and not chosen.auto_book:
        sys.exit(f"DRY_RUN={a.dry_run} so faz alguma coisa com auto_book: true, e '{chosen.title}' tem false: "
                 "nada seria preenchido nem marcado. Repete com --auto-book.")
    dados = config.load_dados(CONFIG_DIR / "dados.json") if chosen.auto_book and a.dry_run != 1 else None
    if a.dry_run == 0:
        log.warning("DRY_RUN=0: se houver horario, ISTO MARCA A SERIO")
    out = run(chosen, dados, a.dry_run,
              int(os.environ.get("CAPTCHA_WAIT_S", "300")), int(os.environ.get("PIN_TIMEOUT_S", "240")))
    print(out.status, out.details)
    for s in out.wanted:
        print("  ", s.label())


if __name__ == "__main__":
    main()
