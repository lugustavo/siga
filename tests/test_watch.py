from datetime import datetime

import pytest

import bot
import config
import notify
import slots
import watch

SEARCH = config.parse_search({"search": {
    "title": "T", "auto_book": True, "entity_opt": 1,
    "service_opt": {"tema": 1, "subtema": 2, "motivo": 3},
    "location_opt": {"distrito": 1, "localidade": 2}}})
SLOT = slots.parse_onclick('guardaDadosDoSlot(1,2,"2026-11-30T14:15:00")', "Local")
CFG = {"dry_run": 0, "max_attempts": 2, "captcha_wait_s": 1, "pin_timeout": 1, "stop_after_booking": True}


@pytest.fixture()
def msgs(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "send", lambda text, photo=None: sent.append(text) or True)
    monkeypatch.setattr(config, "load_dados", lambda path: {"nome": "x"})
    return sent


def fake_run(status, **kw):
    return lambda *a, **k: bot.Outcome(status, [SLOT], [SLOT], SLOT if status == "booked" else None)


def test_notifies_once_for_same_slots(monkeypatch, msgs):
    monkeypatch.setattr(bot, "run", fake_run("slots"))
    state = {"booked": False, "searches": {}}
    watch.tick(SEARCH, state, CFG)
    watch.tick(SEARCH, state, CFG)
    assert len(msgs) == 1 and "30-11-2026 14:15" in msgs[0]


def test_booked_stops_further_booking(monkeypatch, msgs):
    calls = []
    def run(search, dados, dry_run, *a):
        calls.append((dados, dry_run))
        return bot.Outcome("booked", [SLOT], [SLOT], SLOT)
    monkeypatch.setattr(bot, "run", run)
    state = {"booked": False, "searches": {}}
    watch.tick(SEARCH, state, CFG)
    assert state["booked"] and calls[0][0] == {"nome": "x"} and calls[0][1] == 0
    watch.tick(SEARCH, state, CFG)  # ja marcado: so le (dados=None, dry_run=1)
    assert calls[1] == (None, 1)


def test_gives_up_after_max_attempts(monkeypatch, msgs):
    def boom(*a, **k):
        raise bot.CaptchaTimeout("x")
    monkeypatch.setattr(bot, "run", boom)
    state = {"booked": False, "searches": {}}
    watch.tick(SEARCH, state, CFG)
    watch.tick(SEARCH, state, CFG)
    assert state["searches"]["T"]["gave_up"] and any("auto_book desligado" in m for m in msgs)


def test_slot_unavailable_is_not_an_attempt(monkeypatch, msgs):
    def gone(*a, **k):
        raise bot.SlotUnavailable("x")
    monkeypatch.setattr(bot, "run", gone)
    state = {"booked": False, "searches": {}}
    watch.tick(SEARCH, state, CFG)
    assert state["searches"]["T"]["attempts"] == 0


def test_in_hours():
    assert watch.in_hours(SEARCH, datetime(2026, 1, 1, 12, 0))
    assert not watch.in_hours(SEARCH, datetime(2026, 1, 1, 5, 0))
