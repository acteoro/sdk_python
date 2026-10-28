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
