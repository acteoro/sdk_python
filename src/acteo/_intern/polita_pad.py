"""Verificarea politei PAD fara I/O: cererile, interpretarea raspunsului si erorile de asteptare."""

from __future__ import annotations

from ..erori import EroareTimeoutVerificare, EroareValidare, EroareVerificare
from ..modele import Baza, PolitaPadPornita, RezultatPolitaPad
from ..validare import valideaza_cerere_polita_pad
from .cereri import CerereHttp
from .raspunsuri import Raspuns, decodeaza
from .verificari import COD_VERIFICARE_ESUATA, limite_din

CALE = "/api/public/v1/polita-pad"

Referinta = PolitaPadPornita | str


class _CorpEsuat(Baza):
    status: str
    code: str | None = None
    error: str


def cerere_porneste(
    *,
    cnp: str,
    judet: str | None,
    localitate: str | None,
    sector: int | None,
    judet_id: str | None,
    localitate_id: str | None,
    data: str | None,
    acord: bool,
    callback_url: str | None,
) -> CerereHttp:
    """POST: porneste verificarea. Se taxeaza la final, doar daca PADROM raspunde."""
    corp = valideaza_cerere_polita_pad(
        cnp=cnp,
        judet=judet,
        localitate=localitate,
        sector=sector,
        judet_id=judet_id,
        localitate_id=localitate_id,
        data=data,
        acord=acord,
        callback_url=callback_url,
    )
    return CerereHttp("POST", CALE, False, corp=corp)


def id_din(referinta: Referinta) -> str:
    brut = referinta.request_id if isinstance(referinta, PolitaPadPornita) else referinta
    rid = brut.strip() if isinstance(brut, str) else ""
    if not rid:
        raise EroareValidare("Lipseste `request_id` primit de la porneste().", cod="VALIDARE_LOCALA", camp="referinta")
    return rid


def cerere_rezultat(request_id: str) -> CerereHttp:
    """GET: rezultatul dupa id. Nu consuma din cota; CNP-ul nu apare in URL."""
    return CerereHttp("GET", CALE, True, {"id": request_id})


def interpreteaza_pornita(r: Raspuns) -> PolitaPadPornita:
    pornita = decodeaza(PolitaPadPornita, r)
    limite = limite_din(r)
    return pornita.model_copy(update={"limite": limite}) if limite else pornita


def interpreteaza(r: Raspuns) -> RezultatPolitaPad:
    status = r.corp.get("status") if isinstance(r.corp, dict) else None
    if status == "error":
        esuat = decodeaza(_CorpEsuat, r)
        raise EroareVerificare(esuat.error, cod=esuat.code or COD_VERIFICARE_ESUATA, raspuns=r.corp)
    return decodeaza(RezultatPolitaPad, r)


def eroare_depasit(request_id: str, timeout_ms: float) -> EroareTimeoutVerificare:
    return EroareTimeoutVerificare(
        f"Verificarea politei PAD {request_id} nu s-a finalizat in {round(timeout_ms / 1000)} secunde.",
        cod="TIMEOUT_VERIFICARE",
    )
