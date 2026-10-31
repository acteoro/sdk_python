"""Interpreteaza raspunsul HTTP: corpul JSON, eroarea tipata pentru non-2xx, decodarea in modele."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ..erori import (
    EroareAutentificare,
    EroareConflict,
    EroareHttp,
    EroareInterzis,
    EroareLimita,
    EroareNegasit,
    EroarePlanInactiv,
    EroareRaspunsInvalid,
    EroareServer,
    EroareValidare,
    VerificRcaError,
)
from .decodare import cale_eroare

M = TypeVar("M", bound=BaseModel)


@dataclass(frozen=True)
class Raspuns:
    status: int
    headere: Mapping[str, str]
    """Chei lowercase."""
    corp: object

    def header(self, nume: str) -> str | None:
        return self.headere.get(nume.lower())


def citeste_retry_after(headere: Mapping[str, str], acum_ms: int) -> int | None:
    """`Retry-After` vine in secunde sau ca data HTTP."""
    valoare = (headere.get("retry-after") or "").strip()
    if not valoare:
        return None
    try:
        secunde = float(valoare)
    except ValueError:
        pass
    else:
        return max(0, round(secunde * 1000)) if math.isfinite(secunde) else None
    try:
        data = parsedate_to_datetime(valoare)
    except (TypeError, ValueError, IndexError):
        return None
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return max(0, round(data.timestamp() * 1000) - acum_ms)


_OPTIONALE_TEXT = ("hint", "code", "dailyUsage", "monthlyUsage")


def _corp_eroare(corp: object) -> dict[str, Any] | None:
    """Corpul standard de eroare al API-ului, sau None daca nu are forma asteptata."""
    if not isinstance(corp, dict) or not isinstance(corp.get("error"), str):
        return None
    for cheie in _OPTIONALE_TEXT:
        if cheie in corp and not isinstance(corp[cheie], str):
            return None
    acceptate = corp.get("accepted")
    if acceptate is not None and not (isinstance(acceptate, list) and all(isinstance(a, str) for a in acceptate)):
        return None
    limita = corp.get("limita")
    if limita is not None and (isinstance(limita, bool) or not isinstance(limita, (int, float))):
        return None
    return corp


def eroare_din_raspuns(status: int, headere: Mapping[str, str], corp: object, acum_ms: int) -> VerificRcaError:
    """Transforma un raspuns non-2xx in eroarea tipata potrivita."""
    c = _corp_eroare(corp) or {}
    mesaj: str = c.get("error") or f"Cererea a esuat cu HTTP {status}."
    comune: dict[str, Any] = {"status": status, "raspuns": corp, "hint": c.get("hint"), "cod": c.get("code")}

    if status == 400:
        return EroareValidare(mesaj, acceptate=c.get("accepted"), **comune)
    if status == 422:
        # Sursa oficiala refuza valoarea trimisa (ex: NUMAR_RESPINS).
        return EroareValidare(mesaj, **comune)
    if status == 401:
        return EroareAutentificare(mesaj, **comune)
    if status == 402:
        return EroarePlanInactiv(mesaj, **comune)
    if status == 403:
        limita = c.get("limita")
        return EroareInterzis(mesaj, limita=int(limita) if limita is not None else None, **comune)
    if status == 404:
        return EroareNegasit(mesaj, **comune)
    if status == 409:
        return EroareConflict(mesaj, **comune)
    if status == 429:
        zi, luna = c.get("dailyUsage"), c.get("monthlyUsage")
        comune["cod"] = comune["cod"] or ("COTA_ATINSA" if zi or luna else "PREA_MULTE_CERERI")
        return EroareLimita(
            mesaj,
            retry_after_ms=citeste_retry_after(headere, acum_ms),
            utilizare_zi=zi,
            utilizare_luna=luna,
            **comune,
        )
    if status >= 500:
        return EroareServer(mesaj, retry_after_ms=citeste_retry_after(headere, acum_ms), **comune)
    return EroareHttp(mesaj, **comune)


def construieste_raspuns(status: int, headere: Mapping[str, str], continut: bytes, acum_ms: int) -> Raspuns:
    """Citeste corpul JSON; pentru non-2xx arunca eroarea tipata."""
    ok = 200 <= status < 300
    corp: object = None
    if continut:
        try:
            corp = json.loads(continut)
        except ValueError as e:
            text = continut.decode("utf-8", errors="replace")
            if ok:
                raise EroareRaspunsInvalid(
                    "API-ul a raspuns cu un corp care nu e JSON.", status=status, raspuns=text
                ) from e
            corp = text
    if not ok:
        raise eroare_din_raspuns(status, headere, corp, acum_ms)
    return Raspuns(status, headere, corp)


def decodeaza(model: type[M], raspuns: Raspuns) -> M:
    """Decodeaza corpul intr-un model; o nepotrivire devine `EroareRaspunsInvalid`."""
    if not isinstance(raspuns.corp, dict):
        raise EroareRaspunsInvalid(
            "Raspunsul API-ului nu are forma asteptata: corpul nu e un obiect JSON.",
            status=raspuns.status,
            raspuns=raspuns.corp,
        )
    try:
        return model.model_validate(raspuns.corp)
    except ValidationError as e:
        raise EroareRaspunsInvalid(
            f"Raspunsul API-ului nu are forma asteptata: {cale_eroare(e)}",
            status=raspuns.status,
            raspuns=raspuns.corp,
        ) from e
