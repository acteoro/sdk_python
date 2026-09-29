"""Clientul asincron (asyncio, FastAPI, Starlette)."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping

import httpx

from ._intern.ceas import CeasAsync, CeasSistemAsync
from ._intern.http_async import HttpAsync
from ._intern.raspunsuri import decodeaza
from ._intern.setari import SetariRetry, construieste_setari
from ._intern.vehicule import ListaVehicule, Stergere, VehiculCreat, cerere_adauga, cerere_lista, cerere_sterge
from ._intern.verificari import (
    INTERVAL_IMPLICIT_MS,
    TIMEOUT_IMPLICIT_MS,
    Referinta,
    cerere_porneste,
    cerere_rezultat,
    eroare_depasit,
    interpreteaza,
    valideaza_asteptare,
)
from ._versiune import URL_IMPLICIT
from .erori import EroareTimeoutVerificare
from .modele import Vehicul, VerificareFinala, VerificareInCurs
from .tipuri import TipVerificare
from .validare import valideaza_cerere_verificare, valideaza_vehicul_nou


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
        callback_url: str | None = None,
    ) -> VerificareFinala | VerificareInCurs:
        """Porneste o verificare (POST). Consuma o unitate din cota."""
        tinta = valideaza_cerere_verificare(tip, query, serie_sasiu, callback_url)
        inainte = self._ceas.acum_ms()
        raspuns = await self._http.trimite(cerere_porneste(tinta))
        return interpreteaza(raspuns, tinta.serie_sasiu, inainte, self._ceas.acum_ms())

    async def rezultat(self, ref: Referinta) -> VerificareFinala | VerificareInCurs:
        """Interogheaza rezultatul (GET), o singura data. Gratuit."""
        return await self._interogheaza(ref, None)

    async def asteapta(
        self,
        ref: Referinta,
        *,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> VerificareFinala:
        """Interogheaza periodic pana la rezultatul final. Gratuit."""
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
                raspuns = await self._interogheaza(ref, termen)
            except EroareTimeoutVerificare as e:
                raise eroare_depasit(ref, timeout_ms) from e
            if isinstance(raspuns, VerificareFinala):
                return raspuns
        raise eroare_depasit(ref, timeout_ms)

    async def verifica_si_asteapta(
        self,
        *,
        tip: TipVerificare | str,
        query: str,
        serie_sasiu: str | None = None,
        callback_url: str | None = None,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> VerificareFinala:
        """Porneste verificarea si asteapta rezultatul final. Consuma o unitate din cota."""
        raspuns = await self.porneste(tip=tip, query=query, serie_sasiu=serie_sasiu, callback_url=callback_url)
        if isinstance(raspuns, VerificareInCurs):
            return await self.asteapta(raspuns, interval_ms=interval_ms, timeout_ms=timeout_ms)
        return raspuns

    async def _interogheaza(self, ref: Referinta, termen_ms: float | None) -> VerificareFinala | VerificareInCurs:
        raspuns = await self._http.trimite(cerere_rezultat(ref), termen_ms)
        return interpreteaza(raspuns, ref.serie_sasiu, ref.since, self._ceas.acum_ms())


class AsyncClientVehicule:
    """Varianta async a `ClientVehicule`. Il accesezi prin `vrca.vehicule`."""

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
        arr_monitorizat: bool | None = None,
    ) -> Vehicul:
        """Adauga un vehicul in monitorizare. Respecta limita de masini a planului."""
        corp = valideaza_vehicul_nou(numar_inmatriculare, serie_sasiu, arr_monitorizat)
        return decodeaza(VehiculCreat, await self._http.trimite(cerere_adauga(corp))).vehicul

    async def sterge(self, id: str) -> None:
        """Scoate un vehicul din cont, dupa `Vehicul.id`."""
        decodeaza(Stergere, await self._http.trimite(cerere_sterge(id)))


class AsyncVerificRca:
    """Clientul asincron pentru API-ul verificrca.ro.

    >>> async with AsyncVerificRca() as vrca:
    ...     rezultat = await vrca.verificari.verifica_si_asteapta(tip="itp", query="WVWZZZ1JZXW000001")
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = URL_IMPLICIT,
        timeout_ms: float = 30_000,
        retry: SetariRetry | Mapping[str, int] | bool | None = None,
        http_client: httpx.AsyncClient | None = None,
        user_agent: str | None = None,
        _ceas: CeasAsync | None = None,
        _aleator: Callable[[], float] | None = None,
    ) -> None:
        setari = construieste_setari(
            api_key=api_key, base_url=base_url, timeout_ms=timeout_ms, retry=retry, user_agent=user_agent
        )
        self._client_propriu = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=setari.timeout_ms / 1000, follow_redirects=False)
        ceas = _ceas or CeasSistemAsync()
        http = HttpAsync(setari, self._client, ceas, _aleator or random.random)
        self.verificari = AsyncClientVerificari(http, ceas)
        self.vehicule = AsyncClientVehicule(http)

    async def aclose(self) -> None:
        """Inchide conexiunile clientului httpx construit de SDK (nu si pe cel injectat)."""
        if self._client_propriu:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncVerificRca:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
