"""Identificatorii fiecarui document (clientul `Acteo`), transformati in cererea si referinta API-ului.

Fara I/O: clientul sincron si cel async folosesc aceleasi functii. Validarea e cea din
`validare`, deci o cerere respinsa aici nu pleaca pe retea si nu consuma din cota.
"""

from __future__ import annotations

from ..erori import EroareValidare
from ..modele import (
    ReferintaVerificare,
    RezultatArr,
    RezultatItp,
    RezultatRca,
    RezultatRovinieta,
    VerificareInCurs,
    VerificareInCursArr,
    VerificareInCursItp,
    VerificareInCursRca,
    VerificareInCursRovinieta,
)
from ..tipuri import TipVerificare
from ..validare import (
    TintaVerificare,
    este_vin_valid,
    normalizeaza,
    valideaza_cerere_verificare,
    valideaza_identificatori_verificare,
)
from .verificari import Modele, Referinta

MODELE_RCA = Modele(RezultatRca, VerificareInCursRca)
MODELE_ITP = Modele(RezultatItp, VerificareInCursItp)
MODELE_ROVINIETA = Modele(RezultatRovinieta, VerificareInCursRovinieta)
MODELE_ARR = Modele(RezultatArr, VerificareInCursArr)


def _eroare(mesaj: str, camp: str) -> EroareValidare:
    return EroareValidare(mesaj, cod="VALIDARE_LOCALA", camp=camp)


def _text(valoare: object, camp: str) -> str | None:
    """`None` sau textul gol inseamna lipsa; orice alt tip e o eroare de apel."""
    if valoare is None:
        return None
    if not isinstance(valoare, str):
        raise _eroare(f"`{camp}` trebuie sa fie text.", camp)
    return valoare if valoare.strip() else None


def _in_curs(referinta: VerificareInCurs, tip: TipVerificare, *altele: object) -> VerificareInCurs:
    if any(a is not None for a in altele):
        raise _eroare("Trimite fie verificarea in curs, fie identificatorii documentului, nu pe amandoua.", "referinta")
    if referinta.tip is not tip:
        raise _eroare(
            f"Verificarea in curs e de tip {referinta.tip.value}, nu {tip.value}. "
            f"Foloseste clientul documentului {referinta.tip.value}.",
            "referinta",
        )
    return referinta


# --- RCA: numar de inmatriculare, VIN sau amandoua ---


def _rca(identificator: object, numar: object, vin: object) -> tuple[str | None, str | None]:
    """Intoarce (numar, vin). Un text de 17 caractere fara I, O si Q e VIN, altfel numar."""
    if identificator is not None:
        if numar is not None or vin is not None:
            raise _eroare(
                "Trimite identificatorul RCA fie ca text, fie prin `numar` si `vin`, nu in ambele forme.",
                "identificator",
            )
        text = _text(identificator, "identificator")
        if text is None:
            return None, None
        n = normalizeaza(text)
        return (None, n) if este_vin_valid(n) else (n, None)
    return _text(numar, "numar"), _text(vin, "vin")


def _rca_complet(identificator: object, numar: object, vin: object) -> tuple[str | None, str | None]:
    n, v = _rca(identificator, numar, vin)
    if n is None and v is None:
        raise _eroare("Verificarea RCA cere numarul de inmatriculare sau seria de sasiu (VIN).", "numar")
    return n, v


def tinta_rca(identificator: object, numar: object, vin: object, callback_url: str | None) -> TintaVerificare:
    n, v = _rca_complet(identificator, numar, vin)
    if n is not None:
        return valideaza_cerere_verificare(TipVerificare.RCA, n, v, callback_url)
    return valideaza_cerere_verificare(TipVerificare.RCA, v or "", None, callback_url)


def referinta_rca(referinta: object, numar: object, vin: object) -> Referinta:
    if isinstance(referinta, VerificareInCurs):
        return _in_curs(referinta, TipVerificare.RCA, numar, vin)
    n, v = _rca_complet(referinta, numar, vin)
    query, serie = valideaza_identificatori_verificare(TipVerificare.RCA, n or v, v if n else None)
    # Cu VIN, API-ul cauta doar dupa VIN, deci pollingul merge pe VIN.
    return ReferintaVerificare(tip=TipVerificare.RCA, query=serie or query)


# --- ITP: VIN ---


def tinta_itp(vin: object, callback_url: str | None) -> TintaVerificare:
    return valideaza_cerere_verificare(TipVerificare.ITP, _text(vin, "vin") or "", None, callback_url)


def referinta_itp(referinta: object) -> Referinta:
    if isinstance(referinta, VerificareInCurs):
        return _in_curs(referinta, TipVerificare.ITP)
    query, _ = valideaza_identificatori_verificare(TipVerificare.ITP, _text(referinta, "vin"))
    return ReferintaVerificare(tip=TipVerificare.ITP, query=query)


# --- ARR: numar de inmatriculare ---


def tinta_arr(numar: object, callback_url: str | None) -> TintaVerificare:
    return valideaza_cerere_verificare(TipVerificare.ARR, _text(numar, "numar") or "", None, callback_url)


def referinta_arr(referinta: object) -> Referinta:
    if isinstance(referinta, VerificareInCurs):
        return _in_curs(referinta, TipVerificare.ARR)
    query, _ = valideaza_identificatori_verificare(TipVerificare.ARR, _text(referinta, "numar"))
    return ReferintaVerificare(tip=TipVerificare.ARR, query=query)


# --- Rovinieta: numar, VIN si numarul talonului ---


def tinta_rovinieta(numar: object, vin: object, serie_talon: object, callback_url: str | None) -> TintaVerificare:
    return valideaza_cerere_verificare(
        TipVerificare.ROVINIETA,
        _text(numar, "numar") or "",
        _text(vin, "vin"),
        callback_url,
        _text(serie_talon, "serie_talon"),
    )


def referinta_rovinieta(referinta: VerificareInCurs | None, numar: object, vin: object) -> Referinta:
    """Pollingul cere numarul si VIN-ul; numarul talonului nu se trimite."""
    if referinta is not None:
        return _in_curs(referinta, TipVerificare.ROVINIETA, numar, vin)
    query, serie = valideaza_identificatori_verificare(
        TipVerificare.ROVINIETA, _text(numar, "numar"), _text(vin, "vin")
    )
    return ReferintaVerificare(tip=TipVerificare.ROVINIETA, query=query, serie_sasiu=serie)
