"""Timpul, in spatele unei interfete, ca testele sa nu doarma de-adevaratelea."""

from __future__ import annotations

import time
from typing import Protocol

import anyio


class Ceas(Protocol):
    def acum_ms(self) -> int:
        """Timpul curent, ms de la epoca Unix (pentru `since`)."""
        ...

    def monoton_ms(self) -> float:
        """Timp monoton, ms (pentru termene si pauze)."""
        ...

    def dormi_ms(self, ms: float) -> None: ...


class CeasAsync(Protocol):
    def acum_ms(self) -> int: ...

    def monoton_ms(self) -> float: ...

    async def dormi_ms(self, ms: float) -> None: ...


class CeasSistem:
    def acum_ms(self) -> int:
        return time.time_ns() // 1_000_000

    def monoton_ms(self) -> float:
        return time.monotonic() * 1000

    def dormi_ms(self, ms: float) -> None:
        if ms > 0:
            time.sleep(ms / 1000)


class CeasSistemAsync:
    def acum_ms(self) -> int:
        return time.time_ns() // 1_000_000

    def monoton_ms(self) -> float:
        return time.monotonic() * 1000

    async def dormi_ms(self, ms: float) -> None:
        if ms > 0:
            await anyio.sleep(ms / 1000)
