"""Validarea locala a numerelor de inmatriculare, a VIN-urilor si a cererilor.

Aceleasi reguli ca prevalidarea din API. O cerere pe care sursa oficiala ar refuza-o
oricum e oprita aici: nu pleaca pe retea si nu consuma din cota.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .erori import EroareValidare
from .tipuri import TipVerificare

_JUDETE = (
    "AB|AR|AG|BC|BH|BN|BT|BV|BR|BZ|CS|CL|CJ|CT|CV|DB|DJ|GL|GR|GJ|HD|HR"
    "|IL|IS|IF|MM|MH|MS|NT|OT|PH|SM|SJ|SB|SV|TR|TM|TL|VS|VL|VN"
)
# re.ASCII: \d si IGNORECASE doar pe ASCII, altfel cifre arabe ar trece.
_NUMAR = re.compile(
    rf"B\d{{2,3}}[A-Z]{{2,3}}|({_JUDETE})\d{{2}}[A-Z]{{2,3}}|CD\d{{3}}[A-Z]{{1,3}}|TC\d{{4}}[A-Z]{{2}}",
    re.IGNORECASE | re.ASCII,
)
_VIN = re.compile(r"[A-HJ-NPR-Z0-9]{17}", re.IGNORECASE | re.ASCII)
_NUMAR_FLOTA = re.compile(r"[A-Z0-9\s-]*", re.IGNORECASE | re.ASCII)
_SERIE_FLOTA = re.compile(r"[A-Z0-9]*", re.IGNORECASE | re.ASCII)
_SEPARATORI = re.compile(r"[\s\-_]")
_LUNGIME_VIN = 17

TIPURI_VERIFICARE: tuple[TipVerificare, ...] = tuple(TipVerificare)
"""Toate tipurile de verificare acceptate de API, in ordine: rca, itp, rovinieta, arr."""


def normalizeaza(valoare: str) -> str:
    """Aduce un numar sau un VIN la forma canonica: fara spatii, cratime sau underscore, cu majuscule.

    >>> normalizeaza(" b-123 abc ")
    'B123ABC'
    """
    return _SEPARATORI.sub("", valoare.strip().upper())


def este_numar_inmatriculare_valid(valoare: str) -> bool:
    """Verifica un numar romanesc: Bucuresti (B123ABC), judete (CJ45XYZ), CD123A, TC1234AB.

    Accepta si forme cu spatii sau cratime.
    """
    return _NUMAR.fullmatch(normalizeaza(valoare)) is not None


def este_vin_valid(valoare: str) -> bool:
    """Verifica un VIN dupa ISO 3779: exact 17 caractere, cifre si litere, fara I, O si Q."""
    return _VIN.fullmatch(normalizeaza(valoare)) is not None


def _este_numar(valoare: str) -> bool:
    return _NUMAR.fullmatch(valoare) is not None


def _este_vin(valoare: str) -> bool:
    return _VIN.fullmatch(valoare) is not None


def _explica_vin(valoare: str) -> str:
    if not valoare:
        return "Lipseste seria de sasiu (VIN)."
    if len(valoare) != _LUNGIME_VIN:
        return f"Seria de sasiu are {len(valoare)} caractere, sunt necesare exact {_LUNGIME_VIN}."
    return "Seria de sasiu contine caractere neacceptate. Standardul ISO 3779 exclude literele I, O si Q."


def _eroare(mesaj: str, camp: str, acceptate: list[str] | None = None) -> EroareValidare:
    return EroareValidare(mesaj, cod="VALIDARE_LOCALA", camp=camp, acceptate=acceptate)


@dataclass(frozen=True)
class TintaVerificare:
    """Cererea validata si normalizata, gata de trimis la API."""

    tip: TipVerificare
    query: str
    serie_sasiu: str | None
    callback_url: str | None


def _valideaza_callback_url(brut: str | None) -> str | None:
    if brut is None or brut.strip() == "":
        return None
    url = brut.strip()
    if len(url) > 2000:
        raise _eroare("`callback_url` e prea lung (maxim 2000 de caractere).", "callback_url")
    absolut = "`callback_url` trebuie sa fie un URL absolut http(s)."
    try:
        parti = urlsplit(url)
        host = parti.hostname
    except ValueError:
        raise _eroare(absolut, "callback_url") from None
    if not parti.scheme:
        raise _eroare(absolut, "callback_url")
    if parti.scheme.lower() not in ("http", "https"):
        raise _eroare("`callback_url` trebuie sa foloseasca http sau https.", "callback_url")
    if not host:
        raise _eroare(absolut, "callback_url")
    return url


def _valideaza_identificatori(tip: TipVerificare, query: str, serie: str) -> tuple[str, str | None]:
    """Intoarce (query, serie_sasiu) de trimis, sau arunca EroareValidare."""
    if not query:
        raise _eroare("Lipseste `query` (numar de inmatriculare sau serie de sasiu).", "query")

    if tip is TipVerificare.RCA:
        if _este_numar(query):
            if not serie:
                return query, None
            if not _este_vin(serie):
                raise _eroare(f"`serie_sasiu` invalid. {_explica_vin(serie)}", "serie_sasiu")
            return query, serie
        if _este_vin(query):
            return query, None
        raise _eroare(
            "`query` invalid: se accepta un numar de inmatriculare romanesc (ex: B123ABC) sau o serie de sasiu "
            f"de {_LUNGIME_VIN} caractere. {_explica_vin(query)}",
            "query",
        )

    if tip is TipVerificare.ITP:
        if not _este_vin(query) and not _este_vin(serie):
            raise _eroare(
                f"Verificarea ITP cere seria de sasiu (VIN, {_LUNGIME_VIN} caractere). RAR nu cauta dupa numarul "
                f"de inmatriculare. {_explica_vin(serie or query)}",
                "query",
            )
        return query, serie or None

    if tip is TipVerificare.ARR:
        if not _este_numar(query):
            raise _eroare(
                "Verificarea ARR cere numarul de inmatriculare in `query` (ex: B123ABC). ARR nu cauta dupa VIN.",
                "query",
            )
        return query, None

    if not _este_numar(query):
        raise _eroare("Verificarea rovinietei cere numarul de inmatriculare in `query` (ex: B123ABC).", "query")
    if not _este_vin(serie):
        raise _eroare(
            f"Verificarea rovinietei cere si seria de sasiu in `serie_sasiu`. {_explica_vin(serie)}", "serie_sasiu"
        )
    return query, serie


def valideaza_cerere_verificare(
    tip: TipVerificare | str,
    query: str,
    serie_sasiu: str | None = None,
    callback_url: str | None = None,
) -> TintaVerificare:
    """Valideaza si normalizeaza o cerere de verificare, cu aceleasi reguli ca API-ul."""
    try:
        tip_valid = TipVerificare(tip.lower()) if isinstance(tip, str) else TipVerificare(tip)
    except ValueError:
        raise _eroare("`tip` invalid.", "tip", [t.value for t in TIPURI_VERIFICARE]) from None
    q = normalizeaza(query) if isinstance(query, str) else ""
    serie = normalizeaza(serie_sasiu) if isinstance(serie_sasiu, str) else ""
    query_final, serie_finala = _valideaza_identificatori(tip_valid, q, serie)
    return TintaVerificare(tip_valid, query_final, serie_finala, _valideaza_callback_url(callback_url))


def valideaza_vehicul_nou(
    numar_inmatriculare: str | None,
    serie_sasiu: str | None,
    arr_monitorizat: bool | None,
) -> dict[str, object]:
    """Valideaza un vehicul nou cu regulile API-ului si intoarce corpul cererii (chei camelCase)."""
    numar = numar_inmatriculare.strip() if isinstance(numar_inmatriculare, str) else ""
    serie = serie_sasiu.strip() if isinstance(serie_sasiu, str) else ""

    if numar and (len(numar) > 20 or _NUMAR_FLOTA.fullmatch(numar) is None):
        raise _eroare(
            "`numar_inmatriculare` poate contine doar litere, cifre, spatii si cratime (maxim 20).",
            "numar_inmatriculare",
        )
    if serie and (len(serie) > 50 or _SERIE_FLOTA.fullmatch(serie) is None):
        raise _eroare("`serie_sasiu` poate contine doar litere si cifre (maxim 50).", "serie_sasiu")

    numar_norm = re.sub(r"[\s-]+", "", numar.upper())
    serie_norm = serie.upper()
    if not numar_norm and not serie_norm:
        raise _eroare("Trimite numarul de inmatriculare sau seria de sasiu.", "numar_inmatriculare")

    corp: dict[str, object] = {}
    if numar_norm:
        corp["numarInmatriculare"] = numar_norm
    if serie_norm:
        corp["serieSasiu"] = serie_norm
    if arr_monitorizat is not None:
        corp["arrMonitorizat"] = arr_monitorizat
    return corp
