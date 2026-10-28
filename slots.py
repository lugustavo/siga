"""Funcoes puras sobre horarios: ler o onclick dos botoes 'Marcar', filtrar e escolher."""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

# guardaDadosDoSlot(12833,1095,"2026-11-30T14:15:00","<b>Dia: </b>30-11-2026","<b>Hora: </b>14h 15m")
_ONCLICK = re.compile(r'guardaDadosDoSlot\(\s*(\d+)\s*,\s*(\d+)\s*,\s*"([^"]+)"')


@dataclass(frozen=True)
class Slot:
    desk_id: int      # IdMesa
    local_id: int     # IdLocalAtendimento
    local: str        # nome do local (atributo title)
    when: datetime

    @property
    def key(self):
        return f"{self.local_id}|{self.desk_id}|{self.when:%Y-%m-%dT%H:%M}"

    def label(self):
        return f"{self.when:%d-%m-%Y %H:%M} - {self.local}"


def norm(s):
    """Minusculas sem acentos nem espacos repetidos, para comparar textos."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def parse_onclick(onclick, local=""):
    """Slot a partir do onclick do botao 'Marcar'; None se nao for um botao de horario."""
    m = _ONCLICK.search(onclick or "")
    if not m:
        return None
    when = datetime.fromisoformat(m.group(3))
    if when.tzinfo:  # o site mostra a hora no fuso do local de atendimento: guardar essa hora, sem fuso
        when = when.replace(tzinfo=None)
    return Slot(int(m.group(1)), int(m.group(2)), local, when)


def _hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def filter_slots(slots, max_days, slot_start="00:00", slot_end="23:59", now=None):
    """Horarios dentro de 'max_days' dias e com hora em [slot_start, slot_end]."""
    now = now or datetime.now()
    limit = (now + timedelta(days=max_days)).replace(hour=23, minute=59, second=59)
    lo, hi = _hm(slot_start), _hm(slot_end)
    out = [s for s in slots if s.when <= limit and lo <= s.when.hour * 60 + s.when.minute <= hi]
    return sorted(out, key=lambda s: s.when)


def pick(slots, urgency="MAX"):
    """MAX = o mais cedo, MIN = o mais tarde, MED = o do meio (n par: o maior dos dois)."""
    u = (urgency or "MAX").strip().upper()
    if u not in ("MAX", "MED", "MIN"):
        raise ValueError(f"urgency invalida: {urgency!r} (usar MAX, MED ou MIN)")
    ordered = sorted(slots, key=lambda s: s.when)
    if not ordered:
        return None
    return ordered[{"MAX": 0, "MIN": len(ordered) - 1, "MED": len(ordered) // 2}[u]]
