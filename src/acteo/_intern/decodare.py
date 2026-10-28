"""Transforma o eroare Pydantic intr-o cale lizibila, ex: `vehicule[2].createdAt: lipseste`."""

from __future__ import annotations

from pydantic import ValidationError


def cale_eroare(err: ValidationError) -> str:
    prima = err.errors()[0]
    cale = ""
    for parte in prima["loc"]:
        if isinstance(parte, int):
            cale += f"[{parte}]"
        else:
            cale += f".{parte}" if cale else str(parte)
    motiv = "lipseste" if prima["type"] == "missing" else "valoare invalida"
    return f"{cale}: {motiv}" if cale else motiv
