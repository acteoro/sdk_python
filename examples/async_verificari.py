"""Mai multe verificari in paralel cu clientul async."""

import asyncio

from acteo import ActeoError, AsyncActeo


async def main() -> None:
    numere = ["B123ABC", "CJ45XYZ", "B12XYZ"]
    async with AsyncActeo() as acteo:
        rezultate = await asyncio.gather(*(acteo.auto.rca.verifica(n) for n in numere), return_exceptions=True)
    for numar, r in zip(numere, rezultate, strict=True):
        if isinstance(r, ActeoError):
            print(f"{numar}: eroare {type(r).__name__}: {r.mesaj}")
        elif isinstance(r, BaseException):
            raise r
        else:
            print(f"{numar}: {r.status.value}")


asyncio.run(main())
