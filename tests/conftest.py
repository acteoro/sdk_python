"""Unelte comune: ceas fals (fara somn real), server HTTP fals peste httpx.MockTransport."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from verificrca._intern.setari import Setari, SetariRetry, construieste_setari

CHEIE = "vrca_test_0123456789abcdef"
BASE = "https://api.example.com"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def setari_test(**kw: Any) -> Setari:
    valori: dict[str, Any] = {
        "api_key": CHEIE,
        "base_url": BASE,
        "timeout_ms": 30_000,
        "retry": SetariRetry(),
        "user_agent": None,
    }
    valori.update(kw)
    return construieste_setari(**valori)


class CeasFals:
    """Ceas controlat de test: somnul doar avanseaza timpul si se inregistreaza."""

    def __init__(self, epoca_ms: int = 1_700_000_000_000) -> None:
        self.epoca_ms = epoca_ms
        self.t = 0.0
        self.somnuri: list[float] = []

    def acum_ms(self) -> int:
        return self.epoca_ms + int(self.t)

    def monoton_ms(self) -> float:
        return self.t

    def dormi_ms(self, ms: float) -> None:
        self.somnuri.append(ms)
        self.t += max(0.0, ms)


class CeasFalsAsync:
    def __init__(self, epoca_ms: int = 1_700_000_000_000) -> None:
        self.intern = CeasFals(epoca_ms)

    @property
    def somnuri(self) -> list[float]:
        return self.intern.somnuri

    def acum_ms(self) -> int:
        return self.intern.acum_ms()

    def monoton_ms(self) -> float:
        return self.intern.monoton_ms()

    async def dormi_ms(self, ms: float) -> None:
        self.intern.dormi_ms(ms)


def json_raspuns(status: int, corp: object, headere: Mapping[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, json=corp, headers=headere)


class ServerFals:
    """Intoarce raspunsurile (sau arunca exceptiile) in ordine si tine minte cererile."""

    def __init__(self, *raspunsuri: httpx.Response | Exception) -> None:
        self.raspunsuri = list(raspunsuri)
        self.cereri: list[httpx.Request] = []

    def __call__(self, cerere: httpx.Request) -> httpx.Response:
        self.cereri.append(cerere)
        if not self.raspunsuri:
            raise AssertionError(f"Cerere neasteptata: {cerere.method} {cerere.url}")
        urmator = self.raspunsuri.pop(0)
        if isinstance(urmator, Exception):
            raise urmator
        return urmator

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))

    def client_async(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))
