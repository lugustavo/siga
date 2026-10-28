"""Obtem o codigo de validacao enviado pelo SIGA: primeiro por IMAP (Gmail), senao pergunta por Telegram."""
import email
import html
import imaplib
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

import notify

log = logging.getLogger("siga")

# "O seu codigo de validacao e: 56131" (o remetente marca o corpo como HTML)
_KEYED = re.compile(r"c[oó]digo\s+de\s+valida[cç][aã]o\D{0,30}?(\d{4,8})", re.I)
_BARE = re.compile(r"(?<!\d)(\d{5,6})(?!\d)")
_HINT = r"marcacaodeatendimento|c[oó]digo de valida"
_SKEW = timedelta(seconds=120)  # relogios do SIGA e desta maquina podem diferir


def _clean(txt):
    txt = re.sub(r"(?is)<!--.*?-->|<head.*?</head>|<style.*?</style>|<script.*?</script>", " ", txt)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", txt)))


def _body(msg):
    parts = []
    for p in msg.walk():
        if p.get_content_type() in ("text/plain", "text/html"):
            try:
                raw = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")
            except Exception:
                continue
            parts.append(_clean(raw))
    return " ".join(parts)


def extract_pin(text):
    m = _KEYED.search(text) or _BARE.search(text)
    return m.group(1) if m else None


def pin_from_message(msg, hint=None):
    """PIN de uma mensagem (email.message.Message) ou None se nao for o email do SIGA."""
    hint = hint or re.compile(_HINT, re.I)
    subject = str(make_header(decode_header(msg.get("Subject", ""))))
    text = f"{msg.get('From', '')} {subject} {_body(msg)}"
    return extract_pin(text) if hint.search(text) else None


def _imap_poll(since, timeout):
    host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    user, pw = os.environ.get("IMAP_USER"), os.environ.get("IMAP_PASSWORD")
    hint = re.compile(os.environ.get("PIN_HINT", _HINT), re.I)
    imap = imaplib.IMAP4_SSL(host)
    imap.login(user, pw)
    deadline = time.time() + timeout
    day = (since - timedelta(days=1)).strftime("%d-%b-%Y")
    try:
        while time.time() < deadline:
            for folder in ("INBOX", "[Gmail]/Spam"):
                if imap.select(f'"{folder}"', readonly=True)[0] != "OK":
                    continue
                _, data = imap.search(None, "SINCE", day)
                for num in reversed(data[0].split()[-20:]):  # a mais recente primeiro
                    _, raw = imap.fetch(num, "(RFC822)")
                    msg = email.message_from_bytes(raw[0][1])
                    try:
                        when = parsedate_to_datetime(msg["Date"])
                    except Exception:
                        continue
                    if when < since - _SKEW:
                        continue
                    code = pin_from_message(msg, hint)
                    if code:
                        log.info("PIN encontrado por IMAP em '%s'", folder)
                        return code
            time.sleep(5)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return None


def get_pin(since=None, timeout=240):
    """'since' = instante (aware) em que o formulario foi submetido. O popup do SIGA
    dura 5 minutos, por isso 'timeout' (IMAP) mais o fallback do Telegram tem de caber nisso."""
    since = since or datetime.now(timezone.utc)
    started = time.time()
    if os.environ.get("IMAP_USER") and os.environ.get("IMAP_PASSWORD"):
        try:
            code = _imap_poll(since, timeout)
            if code:
                return code
            log.warning("PIN nao chegou por IMAP em %ss", timeout)
        except Exception as exc:
            log.warning("IMAP falhou (%s)", type(exc).__name__)
    left = max(20, 290 - int(time.time() - started))
    reply = notify.ask_text("<b>Codigo de validacao SIGA</b>\nResponde com o codigo que chegou ao teu email "
                            "(o bot esta parado no popup, que expira em poucos minutos).", timeout=left)
    if reply:
        m = re.search(r"\d{4,8}", reply)
        return m.group(0) if m else reply
    return None
