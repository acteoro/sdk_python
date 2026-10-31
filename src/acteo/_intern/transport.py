"""Transforma exceptiile httpx in `EroareRetea`."""

from __future__ import annotations

import httpx

from ..erori import EroareRetea

# Faza de conectare: cererea HTTP sigur nu a plecat spre server.
_NEAJUNSE = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


def eroare_retea(exc: httpx.RequestError, metoda: str, cale: str) -> EroareRetea:
    timeout = isinstance(exc, httpx.TimeoutException)
    mesaj = (
        f"Cererea {metoda} {cale} a depasit timpul de raspuns."
        if timeout
        else f"Cererea {metoda} {cale} nu a primit raspuns: {exc}"
    )
    return EroareRetea(mesaj, timeout=timeout, neajunsa=isinstance(exc, _NEAJUNSE))


def timeout_cerere(timeout_client: httpx.Timeout, minim_ms: float | None) -> httpx.Timeout | None:
    """Timeout-ul unei cereri cu minim propriu: cel al clientului, ridicat la `minim_ms`.

    `None` = cererea foloseste timeout-ul clientului. O faza fara limita ramane fara limita.
    """
    if minim_ms is None:
        return None
    minim = minim_ms / 1000

    def ridica(valoare: float | None) -> float | None:
        return None if valoare is None else max(valoare, minim)

    return httpx.Timeout(
        connect=ridica(timeout_client.connect),
        read=ridica(timeout_client.read),
        write=ridica(timeout_client.write),
        pool=ridica(timeout_client.pool),
    )
