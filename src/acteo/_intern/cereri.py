"""Construieste cererea HTTP (URL, headere, corp) din setari, fara s-o trimita."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from ..erori import EroareValidare
from .setari import Setari


@dataclass(frozen=True)
class CerereHttp:
    metoda: Literal["GET", "POST", "DELETE"]
    cale: str
    idempotenta: bool
    """Cererea poate fi repetata fara efecte in plus (GET, DELETE)."""
    query: Mapping[str, str | None] = field(default_factory=dict)
    corp: Mapping[str, object] | None = None


@dataclass(frozen=True)
class PregatireHttp:
    metoda: str
    url: str
    params: dict[str, str]
    headere: dict[str, str]
    continut: bytes | None


def pregateste(setari: Setari, cerere: CerereHttp) -> PregatireHttp:
    headere = {
        "Authorization": f"Bearer {setari.api_key}",
        "Accept": "application/json",
        "User-Agent": setari.user_agent,
    }
    continut: bytes | None = None
    if cerere.corp is not None:
        try:
            continut = json.dumps(cerere.corp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except UnicodeEncodeError as e:
            raise EroareValidare("Datele trimise contin text care nu e UTF-8 valid.", cod="VALIDARE_LOCALA") from e
        headere["Content-Type"] = "application/json"
    params = {k: v for k, v in cerere.query.items() if v is not None}
    return PregatireHttp(cerere.metoda, setari.base_url + cerere.cale, params, headere, continut)
