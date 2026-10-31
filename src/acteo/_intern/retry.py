"""Cand si cat asteptam intre incercari. Regula de baza: nu repetam un POST care ar fi putut
ajunge la server, pentru ca o verificare se taxeaza."""

from __future__ import annotations

from collections.abc import Callable

from ..erori import EroareLimita, EroareRetea, EroareServer, VerificRcaError
from .setari import SetariRetry

# 502/503/504 fara `cod` vin de la proxy: cererea nu a ajuns la aplicatie.
_CODURI_PROXY = frozenset({502, 503, 504})


def se_poate_reincerca(idempotenta: bool, eroare: VerificRcaError, retry: SetariRetry) -> bool:
    if isinstance(eroare, EroareRetea):
        return idempotenta or eroare.neajunsa
    if isinstance(eroare, EroareServer):
        if idempotenta:
            return True
        # Cu `cod`, a raspuns chiar API-ul si cererea nu s-a taxat. Reincercam doar `OCUPAT`,
        # care trece in cateva secunde; restul nu se rezolva repetand.
        if eroare.cod is not None:
            return eroare.cod == "OCUPAT" and (eroare.retry_after_ms or 0) <= retry.intarziere_maxima_ms
        return eroare.status in _CODURI_PROXY
    if isinstance(eroare, EroareLimita):
        # Doar throttle-ul de polling e trecator; cota si plafonul de flota nu se reseteaza in secunde.
        return (
            idempotenta
            and eroare.cod == "PREA_MULTE_CERERI"
            and (eroare.retry_after_ms or 0) <= retry.intarziere_maxima_ms
        )
    return False


def pauza_ms(retry: SetariRetry, incercare: int, eroare: VerificRcaError, aleator: Callable[[], float]) -> int:
    """Backoff exponential cu jitter [0.8, 1.2], plafonat, dar niciodata sub `Retry-After`."""
    baza = min(retry.intarziere_initiala_ms * 2 ** min(incercare, 30), retry.intarziere_maxima_ms)
    pauza = min(round(baza * (0.8 + aleator() * 0.4)), retry.intarziere_maxima_ms)
    if isinstance(eroare, (EroareLimita, EroareServer)) and eroare.retry_after_ms is not None:
        pauza = max(pauza, eroare.retry_after_ms)
    return int(pauza)
