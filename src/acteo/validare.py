"""Validarea locala a numerelor de inmatriculare, a VIN-urilor, a seriilor de talon si a cererilor.

Aceleasi reguli ca prevalidarea din API. O cerere pe care sursa oficiala ar refuza-o
oricum e oprita aici: nu pleaca pe retea si nu consuma din cota.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import get_args
from urllib.parse import urlsplit

from .erori import EroareValidare
from .tipuri import TipVerificare, UnghiImagine

_JUDETE = (
    "AB|AR|AG|BC|BH|BN|BT|BV|BR|BZ|CS|CL|CJ|CT|CV|DB|DJ|GL|GR|GJ|HD|HR"
    "|IL|IS|IF|MM|MH|MS|NT|OT|PH|SM|SJ|SB|SV|TR|TM|TL|VS|VL|VN"
)
# re.ASCII: \d si IGNORECASE doar pe ASCII, altfel cifre arabe ar trece.
_NUMAR = re.compile(
    rf"B\d{{2,3}}[A-Z]{{2,3}}|({_JUDETE})\d{{2}}[A-Z]{{2,3}}|CD\d{{3}}[A-Z]{{1,3}}|TC\d{{4}}[A-Z]{{2}}",
    re.IGNORECASE | re.ASCII,
)
# Numerele verificate la DGPCI: judet (sau B), cifrele si exact trei litere.
_NUMAR_DGPCI = re.compile(rf"(B\d{{2,3}}|({_JUDETE})\d{{2}})[A-Z]{{3}}", re.IGNORECASE | re.ASCII)
_WILDCARD = re.compile(r"[?*]")
_VIN = re.compile(r"[A-HJ-NPR-Z0-9]{17}", re.IGNORECASE | re.ASCII)
_NUMAR_FLOTA = re.compile(r"[A-Z0-9\s-]*", re.IGNORECASE | re.ASCII)
_SERIE_FLOTA = re.compile(r"[A-Z0-9]*", re.IGNORECASE | re.ASCII)
_SEPARATORI = re.compile(r"[\s\-_]")
_LUNGIME_VIN = 17
_SERIE_TALON = re.compile(r"(?=.*\d)[A-Z0-9]{6,20}", re.ASCII)
_NU_ALFANUMERIC = re.compile(r"[^A-Z0-9]", re.ASCII)
_LUNGIME_MAXIMA_TALON = 30

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


def normalizeaza_serie_talon(valoare: str) -> str:
    """Aduce numarul certificatului de inmatriculare (talon) la forma canonica: doar litere si cifre, cu majuscule.

    >>> normalizeaza_serie_talon(" i 00639603-f ")
    'I00639603F'
    """
    return _NU_ALFANUMERIC.sub("", valoare.upper())


def este_serie_talon_valida(valoare: str) -> bool:
    """Verifica forma numarului certificatului de inmatriculare: 6-20 litere si cifre, cel putin o cifra.

    Numarul e tiparit jos pe talon, la "Numarul certificatului" (ex: I00639603F). Accepta si forme
    cu spatii sau cratime. Validarea completa o face sursa oficiala, impreuna cu numarul si VIN-ul.
    """
    return _SERIE_TALON.fullmatch(normalizeaza_serie_talon(valoare)) is not None


_MESAJ_TALON_INVALID = (
    "`serie_talon` invalid: se asteapta numarul certificatului de inmatriculare, tiparit jos pe talon (ex: I00639603F)."
)


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
    serie_talon: str | None = None
    """Doar la rovinieta."""


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


def _valideaza_serie_talon(tip: TipVerificare, brut: str | None) -> str | None:
    """Seria talonului e ceruta doar la rovinieta; la celelalte tipuri nu se trimite."""
    if tip is not TipVerificare.ROVINIETA:
        return None
    serie = normalizeaza_serie_talon(brut) if isinstance(brut, str) else ""
    if not serie:
        raise _eroare(
            "Verificarea rovinietei cere si numarul certificatului de inmatriculare (talon) in `serie_talon` "
            "(ex: I00639603F).",
            "serie_talon",
        )
    if _SERIE_TALON.fullmatch(serie) is None:
        raise _eroare(_MESAJ_TALON_INVALID, "serie_talon")
    return serie


def valideaza_cerere_verificare(
    tip: TipVerificare | str,
    query: str,
    serie_sasiu: str | None = None,
    callback_url: str | None = None,
    serie_talon: str | None = None,
) -> TintaVerificare:
    """Valideaza si normalizeaza o cerere de verificare, cu aceleasi reguli ca API-ul."""
    try:
        tip_valid = TipVerificare(tip.lower()) if isinstance(tip, str) else TipVerificare(tip)
    except ValueError:
        raise _eroare("`tip` invalid.", "tip", [t.value for t in TIPURI_VERIFICARE]) from None
    q = normalizeaza(query) if isinstance(query, str) else ""
    serie = normalizeaza(serie_sasiu) if isinstance(serie_sasiu, str) else ""
    query_final, serie_finala = _valideaza_identificatori(tip_valid, q, serie)
    talon = _valideaza_serie_talon(tip_valid, serie_talon)
    return TintaVerificare(tip_valid, query_final, serie_finala, _valideaza_callback_url(callback_url), talon)


def valideaza_identificatori_verificare(
    tip: TipVerificare, query: str | None, serie_sasiu: str | None = None
) -> tuple[str, str | None]:
    """Valideaza si normalizeaza doar identificatorii (fara callback si talon), ex: pentru o interogare GET."""
    q = normalizeaza(query) if isinstance(query, str) else ""
    serie = normalizeaza(serie_sasiu) if isinstance(serie_sasiu, str) else ""
    return _valideaza_identificatori(tip, q, serie)


def valideaza_vehicul_nou(
    numar_inmatriculare: str | None,
    serie_sasiu: str | None,
    arr_monitorizat: bool | None,
    serie_talon: str | None = None,
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

    talon = serie_talon.strip() if isinstance(serie_talon, str) else ""
    if len(talon) > _LUNGIME_MAXIMA_TALON:
        raise _eroare(_MESAJ_TALON_INVALID, "serie_talon")
    talon_norm = normalizeaza_serie_talon(talon)
    if talon_norm and _SERIE_TALON.fullmatch(talon_norm) is None:
        raise _eroare(_MESAJ_TALON_INVALID, "serie_talon")

    numar_norm = re.sub(r"[\s-]+", "", numar.upper())
    serie_norm = serie.upper()
    if not numar_norm and not serie_norm:
        raise _eroare("Trimite numarul de inmatriculare sau seria de sasiu.", "numar_inmatriculare")

    corp: dict[str, object] = {}
    if numar_norm:
        corp["numarInmatriculare"] = numar_norm
    if serie_norm:
        corp["serieSasiu"] = serie_norm
    if talon_norm:
        corp["serieTalon"] = talon_norm
    if arr_monitorizat is not None:
        corp["arrMonitorizat"] = arr_monitorizat
    return corp


# --- Produsele cu raspuns sincron ---


def valideaza_vin_decodare(vin: str) -> str:
    """VIN-ul pentru decodare, normalizat, sau `EroareValidare`."""
    n = normalizeaza(vin) if isinstance(vin, str) else ""
    if not _este_vin(n):
        raise _eroare(_explica_vin(n), "vin")
    return n


def valideaza_numar_disponibil(numar: str) -> str:
    """Numarul pentru DGPCI, normalizat, sau `EroareValidare`."""
    brut = numar if isinstance(numar, str) else ""
    if _WILDCARD.search(brut):
        raise _eroare("API-ul verifica un singur numar complet, fara `?` sau `*`.", "numar")
    n = normalizeaza(brut)
    if not n:
        raise _eroare("Lipseste numarul de inmatriculare.", "numar")
    if _NUMAR_DGPCI.fullmatch(n) is None:
        raise _eroare(
            f"Numarul {n} nu e complet: trimite indicativul judetului, cifrele si trei litere (ex: BV07ABC).", "numar"
        )
    return n


UNGHIURI_IMAGINE: tuple[UnghiImagine, ...] = get_args(UnghiImagine)
"""Unghiurile acceptate pentru poza unei masini, primul fiind cel implicit."""

_SEMNE_TEXT_MASINA = frozenset(" ./+&'()-")
_LUNGIME_MAXIMA_TEXT_MASINA = 66


def _valideaza_text_masina(valoare: object, camp: str) -> str:
    if not isinstance(valoare, str):
        raise _eroare(f"Trimite `{camp}` ca text.", camp)
    t = valoare.strip()
    if not t:
        raise _eroare(f"`{camp}` nu poate fi gol.", camp)
    # Lungimea in unitati UTF-16, ca in API.
    if len(t.encode("utf-16-le")) // 2 > _LUNGIME_MAXIMA_TEXT_MASINA:
        raise _eroare(f"`{camp}` are cel mult {_LUNGIME_MAXIMA_TEXT_MASINA} de caractere.", camp)
    # isalnum() = litere si cifre Unicode, ca \p{L}\p{N} din API.
    if not all(c.isalnum() or c in _SEMNE_TEXT_MASINA for c in t):
        raise _eroare(f"`{camp}` poate contine doar litere, cifre, spatii si . / + & ' ( ) -", camp)
    return t


def valideaza_cerere_imagine(
    marca: str, model: str, an: int, unghi: UnghiImagine | str | None = None, umbra: bool | None = None
) -> dict[str, object]:
    """Corpul cererii de poza, validat ca in API."""
    corp: dict[str, object] = {
        "marca": _valideaza_text_masina(marca, "marca"),
        "model": _valideaza_text_masina(model, "model"),
    }
    an_maxim = date.today().year + 1
    intreg = isinstance(an, int) or (isinstance(an, float) and an.is_integer())
    if isinstance(an, bool) or not intreg or not 1950 <= an <= an_maxim:
        raise _eroare(f"`an` trebuie sa fie un numar intreg intre 1950 si {an_maxim}.", "an")
    corp["an"] = int(an)
    if unghi is not None:
        if unghi not in UNGHIURI_IMAGINE:
            raise _eroare(f"`unghi` poate fi: {', '.join(UNGHIURI_IMAGINE)}.", "unghi", list(UNGHIURI_IMAGINE))
        corp["unghi"] = unghi
    if umbra is not None:
        if not isinstance(umbra, bool):
            raise _eroare("Trimite `umbra` ca True sau False.", "umbra")
        corp["umbra"] = umbra
    return corp
