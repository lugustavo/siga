"""Testa os passos do popup (CAPTCHA, PIN, confirmacao) em paginas locais: sem rede, sem tocar no SIGA."""
import pytest

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

import bot  # noqa: E402
import notify  # noqa: E402


@pytest.fixture()
def page():
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        except Exception as exc:  # chromium nao instalado
            pytest.skip(f"chromium indisponivel: {exc}")
        yield browser.new_page()
        browser.close()


PIN_PAGE = """
<div id="ModalCodigo" style="display:block">
  <input type="text" id="codigo"><span id="lbl_erro_codigo"></span>
  <button id="btn_confirmToken" onclick="{onclick}">Confirmar</button>
</div>
"""


def test_step_pin_ok(page, monkeypatch):
    monkeypatch.setattr(bot.pinmod, "get_pin", lambda since, timeout: "56131")
    page.set_content(PIN_PAGE.format(onclick=(
        "document.body.insertAdjacentHTML('beforeend','<h3>Detalhes da marcação</h3>'); "
        "window.sent = document.getElementById('codigo').value")))
    bot.step_pin(page, None, 5)
    assert page.evaluate("window.sent") == "56131"


def test_step_pin_rejected(page, monkeypatch):
    monkeypatch.setattr(bot.pinmod, "get_pin", lambda since, timeout: "00000")
    monkeypatch.setattr(bot, "STEP_TIMEOUT", 3000)
    page.set_content(PIN_PAGE.format(onclick="document.getElementById('lbl_erro_codigo').textContent='Código inválido'"))
    with pytest.raises(bot.PinRejected, match="Código inválido"):
        bot.step_pin(page, None, 5)


def test_step_pin_no_code(page, monkeypatch):
    monkeypatch.setattr(bot.pinmod, "get_pin", lambda since, timeout: None)
    page.set_content(PIN_PAGE.format(onclick=""))
    with pytest.raises(RuntimeError, match="PIN nao obtido"):
        bot.step_pin(page, None, 5)


CONFIRMACAO = """<body><h4>Detalhes da marcação</h4>
<div>30-11-2026 - CRCPCom Óbidos - 14:15 - 14:30</div><p>Entidade: IRN Registo</p>
<div>Código de Marcação: <b>182D36</b></div><button>Realizar uma nova marcação</button></body>"""


def test_read_confirmation(page):
    page.set_content(CONFIRMACAO)
    info = bot.read_confirmation(page)
    assert info["codigo"] == "182D36"
    assert info["resumo"] == "30-11-2026 - CRCPCom Óbidos - 14:15 - 14:30"


CAPTCHA = """
<div id="recapcha"><iframe title="reCAPTCHA" srcdoc="<div id='recaptcha-anchor' role='checkbox'
 onclick=&quot;parent.document.getElementById('g-recaptcha-response').value='tok'&quot;>x</div>"></iframe>
<textarea id="g-recaptcha-response"></textarea></div>
"""


def test_captcha_automatic(page):
    page.set_content(CAPTCHA)
    assert bot.step_captcha(page, 10, "slot") == "automatico"


def test_captcha_challenge_notifies_once_then_manual(page, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "send", lambda text, photo=None: sent.append(text) or True)
    monkeypatch.setattr(bot, "shot", lambda *a, **k: None)
    monkeypatch.setenv("NOVNC_URL", "http://servidor:6080/vnc.html")
    page.route("https://www.google.com/recaptcha/api2/bframe", lambda r: r.fulfill(body="<html></html>", content_type="text/html"))
    html = CAPTCHA.replace("parent.document.getElementById('g-recaptcha-response').value='tok'",
                           "parent.document.getElementById('desafio').style.visibility='visible'")
    page.set_content(html + """<div id="desafio" style="visibility:hidden;position:absolute;top:50px">
        <iframe src="https://www.google.com/recaptcha/api2/bframe" width="300" height="300"></iframe></div>
        <script>setTimeout(() => document.getElementById('g-recaptcha-response').value = 'tok', 3500)</script>""")
    assert bot.step_captcha(page, 15, "slot") == "manual"
    assert len(sent) == 1 and "http://servidor:6080/vnc.html" in sent[0]


def test_captcha_timeout(page):
    page.set_content(CAPTCHA.replace("='tok'", "=''"))
    with pytest.raises(bot.CaptchaTimeout):
        bot.step_captcha(page, 3, "slot")
