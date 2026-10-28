"""Clientul asincron (asyncio, FastAPI, Starlette)."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from typing import TypeVar

import httpx

from ._intern.ceas import CeasAsync, CeasSistemAsync
from ._intern.http_async import HttpAsync
from ._intern.raspunsuri import decodeaza
from ._intern.setari import PROFIL_LEGACY, Profil, SetariRetry, construieste_setari
from ._intern.vehicule import ListaVehicule, Stergere, VehiculCreat, cerere_adauga, cerere_lista, cerere_sterge
from ._intern.verificari import (
    INTERVAL_IMPLICIT_MS,
    MODELE_GENERICE,
    TIMEOUT_IMPLICIT_MS,
    C,
    F,
    Modele,
    Referinta,
    cerere_porneste,
    cerere_rezultat,
    eroare_depasit,
    interpreteaza_ca,
    valideaza_asteptare,
)
from ._versiune import URL_IMPLICIT_LEGACY
from .erori import EroareTimeoutVerificare
from .modele import Vehicul, VerificareFinala, VerificareInCurs
from .tipuri import TipVerificare
from .validare import TintaVerificare, valideaza_cerere_verificare, valideaza_vehicul_nou

_T = TypeVar("_T", bound="_ClientAsincron")


class AsyncClientVerificari:
    """Varianta async a `ClientVerificari`. Il accesezi prin `vrca.verificari`."""

    def __init__(self, http: HttpAsync, ceas: CeasAsync) -> None:
        self._http = http
        self._ceas = ceas

    async def porneste(
        self,
        *,
        tip: TipVerificare | str,
        query: str,
        serie_sasiu: str | None = None,
        serie_talon: str | None = None,
        callback_url: str | None = None,
    ) -> VerificareFinala | VerificareInCurs:
        """Porneste o verificare (POST). Consuma o unitate din cota."""
        tinta = valideaza_cerere_verificare(tip, query, serie_sasiu, callback_url, serie_talon)
        return await self._porneste(tinta, MODELE_GENERICE)

    async def rezultat(self, ref: Referinta) -> VerificareFinala | VerificareInCurs:
        """Interogheaza rezultatul (GET), o singura data. Gratuit."""
        return await self._interogheaza(ref, None, MODELE_GENERICE)

    async def asteapta(
        self,
        ref: Referinta,
        *,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> VerificareFinala:
        """Interogheaza periodic pana la rezultatul final. Gratuit."""
        return await self._asteapta(ref, interval_ms, timeout_ms, MODELE_GENERICE)

    async def verifica_si_asteapta(
        self,
        *,
        tip: TipVerificare | str,
        query: str,
        serie_sasiu: str | None = None,
        serie_talon: str | None = None,
        callback_url: str | None = None,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> VerificareFinala:
        """Porneste verificarea si asteapta rezultatul final. Consuma o unitate din cota."""
        tinta = valideaza_cerere_verificare(tip, query, serie_sasiu, callback_url, serie_talon)
        return await self._verifica_si_asteapta(tinta, interval_ms, timeout_ms, MODELE_GENERICE)

    # Nucleul comun cu clientul `AsyncActeo`: aceleasi cereri, decodate in modelele cerute.

    async def _porneste(self, tinta: TintaVerificare, modele: Modele[F, C]) -> F | C:
        inainte = self._ceas.acum_ms()
        raspuns = await self._http.trimite(cerere_porneste(tinta))
        return interpreteaza_ca(modele, raspuns, tinta.serie_sasiu, inainte, self._ceas.acum_ms())

    async def _verifica_si_asteapta(
        self, tinta: TintaVerificare, interval_ms: float, timeout_ms: float, modele: Modele[F, C]
    ) -> F:
        raspuns = await self._porneste(tinta, modele)
        if isinstance(raspuns, VerificareInCurs):
            return await self._asteapta(raspuns, interval_ms, timeout_ms, modele)
        return raspuns

    async def _asteapta(self, ref: Referinta, interval_ms: float, timeout_ms: float, modele: Modele[F, C]) -> F:
        interval, timeout_ms = valideaza_asteptare(interval_ms, timeout_ms)
        termen = self._ceas.monoton_ms() + timeout_ms
        while True:
            ramas = termen - self._ceas.monoton_ms()
            if ramas <= 0:
                break
            await self._ceas.dormi_ms(min(interval, ramas))
            if self._ceas.monoton_ms() >= termen:
                break
            try:
                raspuns = await self._interogheaza(ref, termen, modele)
            except EroareTimeoutVerificare as e:
                raise eroare_depasit(ref, timeout_ms) from e
            if isinstance(raspuns, VerificareFinala):
                return raspuns
        raise eroare_depasit(ref, timeout_ms)

    async def _interogheaza(self, ref: Referinta, termen_ms: float | None, modele: Modele[F, C]) -> F | C:
        raspuns = await self._http.trimite(cerere_rezultat(ref), termen_ms)
        return interpreteaza_ca(modele, raspuns, ref.serie_sasiu, ref.since, self._ceas.acum_ms())


class AsyncClientVehicule:
    """Varianta async a `ClientVehicule`: `acteo.auto.flota` (sau `vrca.vehicule`)."""

    def __init__(self, http: HttpAsync) -> None:
        self._http = http

    async def lista(self) -> list[Vehicul]:
        """Vehiculele din cont, cu datele de expirare ale documentelor."""
        return decodeaza(ListaVehicule, await self._http.trimite(cerere_lista())).vehicule

    async def adauga(
        self,
        *,
        numar_inmatriculare: str | None = None,
        serie_sasiu: str | None = None,
        serie_talon: str | None = None,
        arr_monitorizat: bool | None = None,
    ) -> Vehicul:
        """Adauga un vehicul in monitorizare. Respecta limita de masini a planului."""
        corp = valideaza_vehicul_nou(numar_inmatriculare, serie_sasiu, arr_monitorizat, serie_talon)
        return decodeaza(VehiculCreat, await self._http.trimite(cerere_adauga(corp))).vehicul

    async def sterge(self, id: str) -> None:
        """Scoate un vehicul din cont, dupa `Vehicul.id`."""
        decodeaza(Stergere, await self._http.trimite(cerere_sterge(id)))


class _ClientAsincron:
    """Setup-ul comun al clientilor async: setari, conexiune httpx, ceas, reincercari."""

    def __init__(
        self,
        *,
        profil: Profil,
        api_key: str | None,
        base_url: str | None,
        timeout_ms: float,
        retry: SetariRetry | Mapping[str, int] | bool | None,
        http_client: httpx.AsyncClient | None,
        user_agent: str | None,
        ceas: CeasAsync | None,
        aleator: Callable[[], float] | None,
    ) -> None:
        setari = construieste_setari(
            api_key=api_key,
            base_url=profil.url_implicit if base_url is None else base_url,
            timeout_ms=timeout_ms,
            retry=retry,
            user_agent=user_agent,
            profil=profil,
        )
        self._client_propriu = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=setari.timeout_ms / 1000, follow_redirects=False)
        self._ceas = ceas or CeasSistemAsync()
        self._http = HttpAsync(setari, self._client, self._ceas, aleator or random.random)

    async def aclose(self) -> None:
        """Inchide conexiunile clientului httpx construit de SDK (nu si pe cel injectat)."""
        if self._client_propriu:
            await self._client.aclose()

    async def __aenter__(self: _T) -> _T:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


class AsyncVerificRca(_ClientAsincron):
    """Clientul asincron legacy, pastrat pentru codul existent; pentru cod nou foloseste `AsyncActeo`.

    >>> async with AsyncVerificRca() as vrca:
    ...     rezultat = await vrca.verificari.verifica_si_asteapta(tip="itp", query="WVWZZZ1JZXW000001")
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = URL_IMPLICIT_LEGACY,
        timeout_ms: float = 30_000,
        retry: SetariRetry | Mapping[str, int] | bool | None = None,
        http_client: httpx.AsyncClient | None = None,
        user_agent: str | None = None,
        _ceas: CeasAsync | None = None,
        _aleator: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(
            profil=PROFIL_LEGACY,
            api_key=api_key,
            base_url=base_url,
            timeout_ms=timeout_ms,
            retry=retry,
            http_client=http_client,
            user_agent=user_agent,
            ceas=_ceas,
            aleator=_aleator,
        )
        self.verificari = AsyncClientVerificari(self._http, self._ceas)
        self.vehicule = AsyncClientVehicule(self._http)
