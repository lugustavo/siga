import email
from datetime import datetime

import pytest

import config
import pin
import slots

# corpo (sem cabecalhos nem dados pessoais) de um email real do SIGA
SIGA_BODY = (
    "<style> body { font-family:'Arial'; font-size:14.5px; } </style> <body>O seu código de validação é: "
    "<b>56131</b><br/><br/>Por favor, insira-o no formulário para continuar o processo.<br/><br/>"
    "Não responda a este email.<br/><br/>Com os melhores cumprimentos,<br/><br/></body>"
    "<img src='https://siga.marcacaodeatendimento.pt/content/images/logo_siga_2.png' />"
)


def _msg(body, frm="siga@marcacaodeatendimento.pt", subject="Código de Validação"):
    m = email.message.EmailMessage()
    m["From"], m["Subject"] = frm, subject
    m.set_content(body, subtype="html")
    return m


def test_pin_from_siga_email():
    assert pin.pin_from_message(_msg(SIGA_BODY)) == "56131"


def test_pin_ignores_other_senders():
    assert pin.pin_from_message(_msg("Your code is 123456", frm="x@y.com", subject="Hello")) is None


def test_pin_ignores_style_numbers():
    assert pin.extract_pin("<style>a{font-size:14.5px}</style>") is None


ONCLICK = 'guardaDadosDoSlot(12833,1095,"2026-11-30T14:15:00","<b>Dia: </b>30-11-2026","<b>Hora: </b>14h 15m")'


def test_parse_onclick():
    s = slots.parse_onclick(ONCLICK, "CRCPCom Óbidos")
    assert (s.desk_id, s.local_id, s.when) == (12833, 1095, datetime(2026, 11, 30, 14, 15))
    assert s.key == "1095|12833|2026-11-30T14:15"
    assert slots.parse_onclick("other()") is None


@pytest.mark.parametrize("suffix", ["Z", "+00:00", "+01:00"])
def test_parse_onclick_drops_timezone(suffix):
    s = slots.parse_onclick(f'guardaDadosDoSlot(1,2,"2026-11-30T14:15:00{suffix}")')
    assert s.when == datetime(2026, 11, 30, 14, 15) and s.when.tzinfo is None
    assert slots.filter_slots([s], 90, now=datetime(2026, 10, 28, 12, 0)) == [s]


def _slots(*iso):
    return [slots.parse_onclick(f'guardaDadosDoSlot(1,2,"{i}")', "L") for i in iso]


NOW = datetime(2026, 10, 28, 12, 0)


def test_filter_max_days_and_hours():
    s = _slots("2026-11-30T14:15:00", "2026-12-30T09:00:00", "2026-11-02T07:30:00")
    got = slots.filter_slots(s, 40, "08:00", "18:00", NOW)
    assert [x.when.day for x in got] == [30]
    assert len(slots.filter_slots(s, 90, now=NOW)) == 3


def test_pick():
    s = _slots("2026-11-03T10:00:00", "2026-11-05T10:00:00", "2026-11-07T10:00:00", "2026-11-09T10:00:00")
    assert slots.pick(s, "MAX").when.day == 3
    assert slots.pick(s, "MIN").when.day == 9
    assert slots.pick(s, "MED").when.day == 7
    assert slots.pick([], "MAX") is None
    with pytest.raises(ValueError):
        slots.pick(s, "X")


def test_norm():
    assert slots.norm("  Óbidos ") == slots.norm("OBIDOS") == "obidos"


def test_repo_search_config_is_valid():
    searches, errors = config.load_searches("search_config.yaml")
    assert not errors and len(searches) == 2 and not any(s.auto_book for s in searches)


def test_parse_search_rejects_bad_values():
    base = {"search": {"entity_opt": 1, "service_opt": {"tema": 1, "subtema": 2, "motivo": 3},
                       "location_opt": {"distrito": 1, "localidade": 2}}}
    assert config.parse_search(base).frequency == 5
    for patch in ({"frequency": 1}, {"max_days": 200}, {"urgency": "x"}, {"start_time": "7h"}):
        with pytest.raises(config.ConfigError):
            config.parse_search({"search": {**base["search"], **patch}})


def test_load_dados(tmp_path):
    f = tmp_path / "d.json"
    ok = '{"nome":"A B","numero":"123456789ZZ0","email":"ab@cd.pt","telemovel":"912 345 678"}'
    f.write_text(ok)
    assert config.load_dados(f)["telemovel"] == "912345678"
    f.write_text(ok.replace("123456789ZZ0", "123"))
    with pytest.raises(config.ConfigError):
        config.load_dados(f)
    f.write_text(ok.replace("912 345 678", "812345678"))
    with pytest.raises(config.ConfigError):
        config.load_dados(f)
