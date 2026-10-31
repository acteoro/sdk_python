"""Decodare VIN, numere disponibile si poze de masini, fara I/O: cererile si interpretarea raspunsului."""

from __future__ import annotations

import math
from typing import TypeVar

from ..erori import EroareTimeoutVerificare, EroareValidare
from ..modele import Baza, DecodareVin, ImagineMasina, NumarDisponibil
from ..tipuri import UnghiImagine
from ..validare import valideaza_cerere_imagine, valideaza_numar_disponibil, valideaza_vin_decodare
from .cereri import CerereHttp
from .raspunsuri import Raspuns, citeste_retry_after, decodeaza
from .verificari import limite_din

CALE_DECODARE_VIN = "/api/public/v1/decodare-vin"
CALE_NUMERE = "/api/public/v1/numere-disponibile"
CALE_IMAGINI = "/api/public/v1/imagini-masini"

# DGPCI raspunde sincron si poate dura pana la doua minute.
TIMEOUT_NUMAR_MS = 150_000
TIMEOUT_IMAGINE_MS = 120_000
"""Cat asteapta implicit `imagini.asteapta()` o poza `in-lucru`."""
# Pauza cand serverul nu trimite `Retry-After` si plafonul de jos, ca sa nu consumam
# plafonul zilnic de poze generice.
PAUZA_IMAGINE_MS = 10_000

P = TypeVar("P", bound=Baza)


def cerere_decodare_vin(vin: str) -> CerereHttp:
    """POST: decodeaza un VIN. Se taxeaza doar cand marca si modelul sunt gasite."""
    return CerereHttp("POST", CALE_DECODARE_VIN, False, corp={"vin": valideaza_vin_decodare(vin)})


def cerere_numar(numar: str) -> CerereHttp:
    """POST: verifica la DGPCI daca un numar e liber. Se taxeaza doar cand DGPCI da un verdict."""
    corp = {"numar": valideaza_numar_disponibil(numar)}
    return CerereHttp("POST", CALE_NUMERE, False, corp=corp, timeout_minim_ms=TIMEOUT_NUMAR_MS)


def cerere_imagine(marca: str, model: str, an: int, unghi: UnghiImagine | str | None, umbra: bool | None) -> CerereHttp:
    """POST: poza unei masini. Se taxeaza doar cand poza e gata."""
    return CerereHttp("POST", CALE_IMAGINI, False, corp=valideaza_cerere_imagine(marca, model, an, unghi, umbra))


def _cu_limite(model: P, r: Raspuns) -> P:
    limite = limite_din(r)
    return model.model_copy(update={"limite": limite}) if limite else model


def interpreteaza_decodare(r: Raspuns) -> DecodareVin:
    return _cu_limite(decodeaza(DecodareVin, r), r)


def interpreteaza_numar(r: Raspuns) -> NumarDisponibil:
    return _cu_limite(decodeaza(NumarDisponibil, r), r)


def interpreteaza_imagine(r: Raspuns, acum_ms: int) -> ImagineMasina:
    imagine = _cu_limite(decodeaza(ImagineMasina, r), r)
    retry_after = citeste_retry_after(r.headere, acum_ms) if imagine.status == "in-lucru" else None
    return imagine.model_copy(update={"retry_after_ms": retry_after}) if retry_after is not None else imagine


def valideaza_timeout_imagine(timeout_ms: float) -> float:
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, (int, float)) or math.isnan(timeout_ms):
        raise EroareValidare("`timeout_ms` trebuie sa fie un numar.", cod="VALIDARE_LOCALA", camp="timeout_ms")
    return timeout_ms


def pauza_imagine(imagine: ImagineMasina) -> int:
    """Pauza pana la urmatoarea cerere a unei poze `in-lucru`: `Retry-After`, dar cel putin 10 secunde."""
    return max(PAUZA_IMAGINE_MS, imagine.retry_after_ms or 0)


def eroare_timeout_imagine(timeout_ms: float) -> EroareTimeoutVerificare:
    return EroareTimeoutVerificare(
        f"Poza nu a fost gata in {round(timeout_ms / 1000)} secunde. Cere-o din nou mai tarziu.",
        cod="TIMEOUT_IMAGINE",
    )
