"""Clientul `AsyncActeo` (asyncio, FastAPI, Starlette): aceeasi suprafata ca `Acteo`, cu `await`."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import httpx

from ._intern import documente, produse
from ._intern.ceas import CeasAsync
from ._intern.http_async import HttpAsync
from ._intern.setari import PROFIL_ACTEO, SetariRetry
from ._intern.verificari import INTERVAL_IMPLICIT_MS, TIMEOUT_IMPLICIT_MS
from .client_acteo import ClientWebhooks
from .client_async import AsyncClientVehicule, AsyncClientVerificari, _ClientAsincron
from .modele import (
    DecodareVin,
    ImagineMasina,
    NumarDisponibil,
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
from .tipuri import UnghiImagine


class AsyncClientRca:
    """Varianta async a `ClientRca`. Asigurarea RCA, din baza AIDA. Il accesezi prin `acteo.auto.rca`.

    Identificatorul: un text (17 caractere fara I, O si Q = VIN, altfel numar de inmatriculare)
    sau `numar=` si `vin=`; cu amandoua, cautarea in AIDA e mai exacta.
    `verifica()` si `porneste()` consuma din cota; `rezultat()` si `asteapta()` sunt gratuite.
    """

    def __init__(self, verificari: AsyncClientVerificari) -> None:
        self._v = verificari

    async def verifica(
        self,
        identificator: str | None = None,
        /,
        *,
        numar: str | None = None,
        vin: str | None = None,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> RezultatRca:
        """Verifica RCA-ul si asteapta rezultatul final de la sursa oficiala."""
        tinta = documente.tinta_rca(identificator, numar, vin, None)
        return await self._v._verifica_si_asteapta(tinta, interval_ms, timeout_ms, documente.MODELE_RCA)

    async def porneste(
        self,
        identificator: str | None = None,
        /,
        *,
        numar: str | None = None,
        vin: str | None = None,
        callback_url: str | None = None,
    ) -> RezultatRca | VerificareInCursRca:
        """Porneste verificarea fara sa astepte: rezultatul final sau `status == "processing"`."""
        tinta = documente.tinta_rca(identificator, numar, vin, callback_url)
        return await self._v._porneste(tinta, documente.MODELE_RCA)

    async def rezultat(
        self,
        referinta: VerificareInCurs | str | None = None,
        /,
        *,
        numar: str | None = None,
        vin: str | None = None,
    ) -> RezultatRca | VerificareInCursRca:
        """Interogheaza o singura data rezultatul, dupa verificarea in curs sau identificator. Gratuit."""
        ref = documente.referinta_rca(referinta, numar, vin)
        return await self._v._interogheaza(ref, None, documente.MODELE_RCA)

    async def asteapta(
        self,
        referinta: VerificareInCurs | str | None = None,
        /,
        *,
        numar: str | None = None,
        vin: str | None = None,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> RezultatRca:
        """Interogheaza periodic pana la rezultatul final. Gratuit."""
        ref = documente.referinta_rca(referinta, numar, vin)
        return await self._v._asteapta(ref, interval_ms, timeout_ms, documente.MODELE_RCA)


class AsyncClientItp:
    """Inspectia tehnica periodica, din RAR. Il accesezi prin `acteo.auto.itp`. Cere VIN-ul."""

    def __init__(self, verificari: AsyncClientVerificari) -> None:
        self._v = verificari

    async def verifica(
        self, vin: str, *, interval_ms: float = INTERVAL_IMPLICIT_MS, timeout_ms: float = TIMEOUT_IMPLICIT_MS
    ) -> RezultatItp:
        """Verifica ITP-ul si asteapta rezultatul final de la sursa oficiala."""
        tinta = documente.tinta_itp(vin, None)
        return await self._v._verifica_si_asteapta(tinta, interval_ms, timeout_ms, documente.MODELE_ITP)

    async def porneste(self, vin: str, *, callback_url: str | None = None) -> RezultatItp | VerificareInCursItp:
        """Porneste verificarea fara sa astepte: rezultatul final sau `status == "processing"`."""
        return await self._v._porneste(documente.tinta_itp(vin, callback_url), documente.MODELE_ITP)

    async def rezultat(self, referinta: VerificareInCurs | str, /) -> RezultatItp | VerificareInCursItp:
        """Interogheaza o singura data rezultatul, dupa verificarea in curs sau VIN. Gratuit."""
        return await self._v._interogheaza(documente.referinta_itp(referinta), None, documente.MODELE_ITP)

    async def asteapta(
        self,
        referinta: VerificareInCurs | str,
        /,
        *,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> RezultatItp:
        """Interogheaza periodic pana la rezultatul final. Gratuit."""
        ref = documente.referinta_itp(referinta)
        return await self._v._asteapta(ref, interval_ms, timeout_ms, documente.MODELE_ITP)


class AsyncClientRovinieta:
    """Rovinieta, din CNAIR. Il accesezi prin `acteo.auto.rovinieta`.

    Cere numarul de inmatriculare, VIN-ul si numarul certificatului de inmatriculare (talon).
    """

    def __init__(self, verificari: AsyncClientVerificari) -> None:
        self._v = verificari

    async def verifica(
        self,
        *,
        numar: str,
        vin: str,
        serie_talon: str,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> RezultatRovinieta:
        """Verifica rovinieta si asteapta rezultatul final de la sursa oficiala."""
        tinta = documente.tinta_rovinieta(numar, vin, serie_talon, None)
        return await self._v._verifica_si_asteapta(tinta, interval_ms, timeout_ms, documente.MODELE_ROVINIETA)

    async def porneste(
        self, *, numar: str, vin: str, serie_talon: str, callback_url: str | None = None
    ) -> RezultatRovinieta | VerificareInCursRovinieta:
        """Porneste verificarea fara sa astepte: rezultatul final sau `status == "processing"`."""
        tinta = documente.tinta_rovinieta(numar, vin, serie_talon, callback_url)
        return await self._v._porneste(tinta, documente.MODELE_ROVINIETA)

    async def rezultat(
        self,
        referinta: VerificareInCurs | None = None,
        /,
        *,
        numar: str | None = None,
        vin: str | None = None,
        serie_talon: str | None = None,
    ) -> RezultatRovinieta | VerificareInCursRovinieta:
        """Interogheaza o singura data rezultatul. Gratuit.

        Primeste verificarea in curs sau `numar` si `vin`; `serie_talon` e acceptat ca sa poti
        trimite aceleasi argumente ca la `verifica()`, dar interogarea nu il foloseste.
        """
        ref = documente.referinta_rovinieta(referinta, numar, vin)
        return await self._v._interogheaza(ref, None, documente.MODELE_ROVINIETA)

    async def asteapta(
        self,
        referinta: VerificareInCurs | None = None,
        /,
        *,
        numar: str | None = None,
        vin: str | None = None,
        serie_talon: str | None = None,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> RezultatRovinieta:
        """Interogheaza periodic pana la rezultatul final. Gratuit."""
        ref = documente.referinta_rovinieta(referinta, numar, vin)
        return await self._v._asteapta(ref, interval_ms, timeout_ms, documente.MODELE_ROVINIETA)


class AsyncClientArr:
    """Copia conforma ARR. Il accesezi prin `acteo.auto.arr`. Cere numarul de inmatriculare."""

    def __init__(self, verificari: AsyncClientVerificari) -> None:
        self._v = verificari

    async def verifica(
        self, numar: str, *, interval_ms: float = INTERVAL_IMPLICIT_MS, timeout_ms: float = TIMEOUT_IMPLICIT_MS
    ) -> RezultatArr:
        """Verifica copia conforma ARR si asteapta rezultatul final de la sursa oficiala."""
        tinta = documente.tinta_arr(numar, None)
        return await self._v._verifica_si_asteapta(tinta, interval_ms, timeout_ms, documente.MODELE_ARR)

    async def porneste(self, numar: str, *, callback_url: str | None = None) -> RezultatArr | VerificareInCursArr:
        """Porneste verificarea fara sa astepte: rezultatul final sau `status == "processing"`."""
        return await self._v._porneste(documente.tinta_arr(numar, callback_url), documente.MODELE_ARR)

    async def rezultat(self, referinta: VerificareInCurs | str, /) -> RezultatArr | VerificareInCursArr:
        """Interogheaza o singura data rezultatul, dupa verificarea in curs sau numar. Gratuit."""
        return await self._v._interogheaza(documente.referinta_arr(referinta), None, documente.MODELE_ARR)

    async def asteapta(
        self,
        referinta: VerificareInCurs | str,
        /,
        *,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> RezultatArr:
        """Interogheaza periodic pana la rezultatul final. Gratuit."""
        ref = documente.referinta_arr(referinta)
        return await self._v._asteapta(ref, interval_ms, timeout_ms, documente.MODELE_ARR)


class AsyncClientVin:
    """Varianta async a `ClientVin`. Decodarea seriei de sasiu (VIN), prin `acteo.auto.vin`."""

    def __init__(self, http: HttpAsync) -> None:
        self._http = http

    async def decodeaza(self, vin: str) -> DecodareVin:
        """Decodeaza un VIN: marca, model, an si structura lui. Consuma din cota doar cand e `taxat`."""
        return produse.interpreteaza_decodare(await self._http.trimite(produse.cerere_decodare_vin(vin)))


class AsyncClientNumere:
    """Varianta async a `ClientNumere`. Numerele disponibile la DGPCI, prin `acteo.auto.numere`."""

    def __init__(self, http: HttpAsync) -> None:
        self._http = http

    async def verifica(self, numar: str) -> NumarDisponibil:
        """Verifica la DGPCI daca un numar e liber. Timeout de cel putin 150 de secunde pe cerere."""
        return produse.interpreteaza_numar(await self._http.trimite(produse.cerere_numar(numar)))


class AsyncClientImagini:
    """Varianta async a `ClientImagini`. Pozele de studio ale masinilor, prin `acteo.auto.imagini`."""

    def __init__(self, http: HttpAsync, ceas: CeasAsync) -> None:
        self._http = http
        self._ceas = ceas

    async def obtine(
        self, *, marca: str, model: str, an: int, unghi: UnghiImagine | None = None, umbra: bool | None = None
    ) -> ImagineMasina:
        """Cere poza unei masini si raspunde imediat. Se taxeaza doar cu `status == "gata"`."""
        cerere = produse.cerere_imagine(marca, model, an, unghi, umbra)
        return produse.interpreteaza_imagine(await self._http.trimite(cerere), self._ceas.acum_ms())

    async def asteapta(
        self,
        *,
        marca: str,
        model: str,
        an: int,
        unghi: UnghiImagine | None = None,
        umbra: bool | None = None,
        timeout_ms: float = produse.TIMEOUT_IMAGINE_MS,
    ) -> ImagineMasina:
        """Ca `obtine()`, dar cat timp poza e `"in-lucru"` o cere din nou, cu pauzele din `Retry-After`.

        Peste `timeout_ms` (implicit 2 minute) arunca `EroareTimeoutVerificare`.
        """
        timeout_ms = produse.valideaza_timeout_imagine(timeout_ms)
        cerere = produse.cerere_imagine(marca, model, an, unghi, umbra)
        termen = self._ceas.monoton_ms() + timeout_ms
        while True:
            imagine = produse.interpreteaza_imagine(await self._http.trimite(cerere), self._ceas.acum_ms())
            if imagine.status != "in-lucru":
                return imagine
            pauza = produse.pauza_imagine(imagine)
            if self._ceas.monoton_ms() + pauza > termen:
                raise produse.eroare_timeout_imagine(timeout_ms)
            await self._ceas.dormi_ms(pauza)


class AsyncClientAuto:
    """Domeniul auto: documentele unei masini (RCA, ITP, rovinieta, ARR), flota, VIN, numere si poze."""

    def __init__(
        self, verificari: AsyncClientVerificari, vehicule: AsyncClientVehicule, http: HttpAsync, ceas: CeasAsync
    ) -> None:
        self.rca = AsyncClientRca(verificari)
        """Asigurarea RCA: `acteo.auto.rca.verifica("B123ABC")`."""
        self.itp = AsyncClientItp(verificari)
        """ITP: `acteo.auto.itp.verifica("WVWZZZ1JZXW000001")`."""
        self.rovinieta = AsyncClientRovinieta(verificari)
        """Rovinieta: `acteo.auto.rovinieta.verifica(numar=..., vin=..., serie_talon=...)`."""
        self.arr = AsyncClientArr(verificari)
        """Copia conforma ARR: `acteo.auto.arr.verifica("B123ABC")`."""
        self.flota = vehicule
        """Vehiculele monitorizate din cont: `lista()`, `adauga()`, `sterge()`."""
        self.vin = AsyncClientVin(http)
        """Decodarea VIN: `await acteo.auto.vin.decodeaza("WVWZZZ1KZBW000000")`."""
        self.numere = AsyncClientNumere(http)
        """Numere disponibile la DGPCI: `await acteo.auto.numere.verifica("BV07ABC")`."""
        self.imagini = AsyncClientImagini(http, ceas)
        """Pozele masinilor: `await acteo.auto.imagini.obtine(marca=..., model=..., an=...)`."""


class AsyncActeo(_ClientAsincron):
    """Clientul asincron al API-ului Acteo, organizat pe domenii.

    >>> async with AsyncActeo() as acteo:  # cheia din ACTEO_API_KEY
    ...     rca = await acteo.auto.rca.verifica("B123ABC")

    `acteo.auto.rca`, `.itp`, `.rovinieta`, `.arr`, `acteo.auto.flota`, `.vin`, `.numere`,
    `.imagini` si `acteo.webhooks`.
    Cheia vine din `api_key`, altfel din `ACTEO_API_KEY`, apoi din `VERIFICRCA_API_KEY`.
    `http_client` permite un `httpx.AsyncClient` propriu; SDK-ul nu il inchide. Constructorul nu
    face cereri pe retea.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_ms: float = 30_000,
        retry: SetariRetry | Mapping[str, int] | bool | None = None,
        http_client: httpx.AsyncClient | None = None,
        user_agent: str | None = None,
        _ceas: CeasAsync | None = None,
        _aleator: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(
            profil=PROFIL_ACTEO,
            api_key=api_key,
            base_url=base_url,
            timeout_ms=timeout_ms,
            retry=retry,
            http_client=http_client,
            user_agent=user_agent,
            ceas=_ceas,
            aleator=_aleator,
        )
        self.auto = AsyncClientAuto(
            AsyncClientVerificari(self._http, self._ceas), AsyncClientVehicule(self._http), self._http, self._ceas
        )
        """Documentele unei masini, flota, VIN, numere si poze."""
        self.webhooks = ClientWebhooks()
        """Citirea webhook-urilor."""
