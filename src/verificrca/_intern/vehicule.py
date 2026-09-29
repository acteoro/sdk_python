"""Cererile si formele raspunsurilor pentru flota."""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from ..erori import EroareValidare
from ..modele import Baza, Vehicul
from .cereri import CerereHttp

CALE = "/api/public/v1/vehicule"


class ListaVehicule(Baza):
    vehicule: list[Vehicul]


class VehiculCreat(Baza):
    vehicul: Vehicul


class Stergere(Baza):
    success: Literal[True]


def cerere_lista() -> CerereHttp:
    return CerereHttp("GET", CALE, True)


def cerere_adauga(corp: dict[str, object]) -> CerereHttp:
    return CerereHttp("POST", CALE, False, corp=corp)


def cerere_sterge(id: str) -> CerereHttp:
    curat = id.strip() if isinstance(id, str) else ""
    if not curat:
        raise EroareValidare("Lipseste ID-ul vehiculului.", camp="id", cod="VALIDARE_LOCALA")
    return CerereHttp("DELETE", f"{CALE}/{quote(curat, safe='')}", True)
