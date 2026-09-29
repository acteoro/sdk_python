"""Mai multe verificari in paralel cu clientul async."""

import asyncio

from verificrca import AsyncVerificRca, VerificRcaError


async def main() -> None:
    numere = ["B123ABC", "CJ45XYZ", "B12XYZ"]
    async with AsyncVerificRca() as vrca:
        rezultate = await asyncio.gather(
            *(vrca.verificari.verifica_si_asteapta(tip="rca", query=n) for n in numere), return_exceptions=True
        )
    for numar, r in zip(numere, rezultate, strict=True):
        if isinstance(r, VerificRcaError):
            print(f"{numar}: eroare {type(r).__name__}: {r.mesaj}")
        elif isinstance(r, BaseException):
            raise r
        else:
            print(f"{numar}: {r.status.value}")


asyncio.run(main())
