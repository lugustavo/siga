"""Leitura e validacao de search_config.yaml e config/dados.json."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_HHMM = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_EMAIL = re.compile(r"^[0-9a-zA-Z_][\w.-]*[a-zA-Z0-9_]@[a-zA-Z0-9][\w.-]*[a-zA-Z0-9]\.[a-zA-Z][a-zA-Z.]*[a-zA-Z]$")
_MOVEL = re.compile(r"^9[1236]\d{7}$")
_FIXO = re.compile(r"^[239]\d{8}$")
_TIPOS_ID = ("NIS", "CC", "BI", "NIF", "PA", "AR")


class ConfigError(ValueError):
    pass


@dataclass
class Search:
    title: str
    entity: object
    tema: object
    subtema: object
    motivo: object
    distrito: object
    localidade: object
    local_atendimento: object = None
    qtd_casos: int = 1
    start_time: str = "07:00"
    end_time: str = "23:59"
    slot_start: str = "00:00"
    slot_end: str = "23:59"
    max_days: int = 90
    frequency: int = 5
    urgency: str = "MAX"
    auto_book: bool = False
    raw: dict = field(default_factory=dict, repr=False)


def _hhmm(value, name, where):
    if not isinstance(value, str) or not _HHMM.match(value):
        raise ConfigError(f"{where}: '{name}' tem de ser HH:MM (recebido {value!r})")
    return value


def _required(d, key, where):
    if d.get(key) in (None, ""):
        raise ConfigError(f"{where}: falta '{key}'")
    return d[key]


def parse_search(item, index=1):
    where = f"configuracao #{index}"
    cfg = item.get("search") if isinstance(item, dict) else None
    if not isinstance(cfg, dict):
        raise ConfigError(f"{where}: esperado um bloco 'search:'")
    service = cfg.get("service_opt") or {}
    location = cfg.get("location_opt") or {}
    s = Search(
        title=str(cfg.get("title") or f"Pesquisa {index}"),
        entity=_required(cfg, "entity_opt", where),
        tema=_required(service, "tema", f"{where} service_opt"),
        subtema=_required(service, "subtema", f"{where} service_opt"),
        motivo=_required(service, "motivo", f"{where} service_opt"),
        distrito=_required(location, "distrito", f"{where} location_opt"),
        localidade=_required(location, "localidade", f"{where} location_opt"),
        local_atendimento=location.get("local_atendimento"),
        qtd_casos=int(service.get("qtd_casos", 1)),
        start_time=_hhmm(cfg.get("start_time", "07:00"), "start_time", where),
        end_time=_hhmm(cfg.get("end_time", "23:59"), "end_time", where),
        slot_start=_hhmm(cfg.get("slot_start", "00:00"), "slot_start", where),
        slot_end=_hhmm(cfg.get("slot_end", "23:59"), "slot_end", where),
        max_days=int(cfg.get("max_days", 90)),
        frequency=int(cfg.get("frequency", 5)),
        urgency=str(cfg.get("urgency", "MAX")).strip().upper(),
        auto_book=bool(cfg.get("auto_book", False)),
        raw=cfg,
    )
    if not 1 <= s.qtd_casos <= 5:
        raise ConfigError(f"{where}: qtd_casos entre 1 e 5")
    if not 1 <= s.max_days <= 90:
        raise ConfigError(f"{where}: max_days entre 1 e 90")
    if not 2 <= s.frequency <= 120:
        raise ConfigError(f"{where}: frequency (minutos) entre 2 e 120")
    if s.urgency not in ("MAX", "MED", "MIN"):
        raise ConfigError(f"{where}: urgency tem de ser MAX, MED ou MIN")
    return s


def load_searches(path="search_config.yaml"):
    """Lista de Search validas; configuracoes invalidas sao devolvidas em 'errors'."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ConfigError(f"{path}: esperada uma lista de '- search:'")
    searches, errors = [], []
    for i, item in enumerate(data, start=1):
        try:
            searches.append(parse_search(item, i))
        except (ConfigError, ValueError, TypeError) as exc:
            errors.append(str(exc))
    return searches, errors


def load_dados(path):
    """Dados pessoais para o formulario de marcacao (validados como o site valida)."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path} nao existe (copiar de config/dados.example.json)")
    tipo = str(d.get("tipo_identificacao", "CC")).upper()
    numero = re.sub(r"\s", "", str(d.get("numero", "")))
    out = {
        "nome": str(d.get("nome", "")).strip(),
        "tipo_identificacao": tipo,
        "numero": numero,
        "email": str(d.get("email", "")).strip(),
        "telemovel": re.sub(r"\D", "", str(d.get("telemovel", ""))),
        "telefone": re.sub(r"\D", "", str(d.get("telefone", ""))),
    }
    if not out["nome"]:
        raise ConfigError("dados.json: falta 'nome'")
    if tipo not in _TIPOS_ID:
        raise ConfigError(f"dados.json: tipo_identificacao tem de ser um de {_TIPOS_ID}")
    if not numero or (tipo == "CC" and len(numero) != 12):
        raise ConfigError("dados.json: 'numero' invalido (o CC tem 12 caracteres, ex. 123456789ZZ0)")
    if not (out["email"] or out["telemovel"]):
        raise ConfigError("dados.json: indicar 'email' ou 'telemovel'")
    if out["email"] and not _EMAIL.match(out["email"]):
        raise ConfigError("dados.json: 'email' invalido")
    if out["telemovel"] and not _MOVEL.match(out["telemovel"]):
        raise ConfigError("dados.json: 'telemovel' invalido (9 digitos, comeca por 91, 92, 93 ou 96)")
    if out["telefone"] and not _FIXO.match(out["telefone"]):
        raise ConfigError("dados.json: 'telefone' invalido (9 digitos, comeca por 2, 3 ou 9)")
    return out
