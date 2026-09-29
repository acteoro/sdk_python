"""Clientul sincron."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping

import httpx

from ._intern.ceas import Ceas, CeasSistem
from ._intern.http_sync import Http
from ._intern.setari import SetariRetry, construieste_setari
from ._intern.verificari import (
    INTERVAL_IMPLICIT_MS,
    INTERVAL_MINIM_MS,
    TIMEOUT_IMPLICIT_MS,
    Referinta,
    cerere_porneste,
    cerere_rezultat,
    eroare_depasit,
    interpreteaza,
)
from ._versiune import URL_IMPLICIT
from .erori import EroareTimeoutVerificare
from .modele import VerificareFinala, VerificareInCurs
from .tipuri import TipVerificare
from .validare import valideaza_cerere_verificare


class ClientVerificari:
    """Verificarile la cerere: RCA, ITP, rovinieta si ARR. Il accesezi prin `vrca.verificari`.

    Doar `porneste()` si `verifica_si_asteapta()` consuma din cota planului API.
    `rezultat()` si `asteapta()` sunt gratuite.
    """

    def __init__(self, http: Http, ceas: Ceas) -> None:
        self._http = http
        self._ceas = ceas

    def porneste(
        self,
        *,
        tip: TipVerificare | str,
        query: str,
        serie_sasiu: str | None = None,
        callback_url: str | None = None,
    ) -> VerificareFinala | VerificareInCurs:
        """Porneste o verificare (POST). Consuma o unitate din cota.

        Intoarce rezultatul final sau `VerificareInCurs` (`status == "processing"`).
        """
        tinta = valideaza_cerere_verificare(tip, query, serie_sasiu, callback_url)
        inainte = self._ceas.acum_ms()
        raspuns = self._http.trimite(cerere_porneste(tinta))
        return interpreteaza(raspuns, tinta.serie_sasiu, inainte, self._ceas.acum_ms())

    def rezultat(self, ref: Referinta) -> VerificareFinala | VerificareInCurs:
        """Interogheaza rezultatul (GET), o singura data. Gratuit."""
        return self._interogheaza(ref, None)

    def asteapta(
        self,
        ref: Referinta,
        *,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> VerificareFinala:
        """Interogheaza periodic pana la rezultatul final. Gratuit.

        `interval_ms` are minim 2000. Peste `timeout_ms` arunca `EroareTimeoutVerificare`.
        """
        interval = max(INTERVAL_MINIM_MS, interval_ms)
        termen = self._ceas.monoton_ms() + timeout_ms
        while True:
            ramas = termen - self._ceas.monoton_ms()
            if ramas <= 0:
                break
            self._ceas.dormi_ms(min(interval, ramas))
            if self._ceas.monoton_ms() >= termen:
                break
            try:
                raspuns = self._interogheaza(ref, termen)
            except EroareTimeoutVerificare as e:
                raise eroare_depasit(ref, timeout_ms) from e
            if isinstance(raspuns, VerificareFinala):
                return raspuns
        raise eroare_depasit(ref, timeout_ms)

    def verifica_si_asteapta(
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
        raspuns = self.porneste(tip=tip, query=query, serie_sasiu=serie_sasiu, callback_url=callback_url)
        if isinstance(raspuns, VerificareInCurs):
            return self.asteapta(raspuns, interval_ms=interval_ms, timeout_ms=timeout_ms)
        return raspuns

    def _interogheaza(self, ref: Referinta, termen_ms: float | None) -> VerificareFinala | VerificareInCurs:
        raspuns = self._http.trimite(cerere_rezultat(ref), termen_ms)
        return interpreteaza(raspuns, ref.serie_sasiu, ref.since, self._ceas.acum_ms())


class VerificRca:
    """Clientul sincron pentru API-ul verificrca.ro.

    >>> with VerificRca() as vrca:  # cheia din VERIFICRCA_API_KEY
    ...     rezultat = vrca.verificari.verifica_si_asteapta(tip="rca", query="B123ABC")

    `http_client` permite un `httpx.Client` propriu (proxy, certificate); timeout-ul lui ramane
    al lui si SDK-ul nu il inchide. Constructorul nu face cereri pe retea.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = URL_IMPLICIT,
        timeout_ms: float = 30_000,
        retry: SetariRetry | Mapping[str, int] | bool | None = None,
        http_client: httpx.Client | None = None,
        user_agent: str | None = None,
        _ceas: Ceas | None = None,
        _aleator: Callable[[], float] | None = None,
    ) -> None:
        setari = construieste_setari(
            api_key=api_key, base_url=base_url, timeout_ms=timeout_ms, retry=retry, user_agent=user_agent
        )
        self._client_propriu = http_client is None
        self._client = http_client or httpx.Client(timeout=setari.timeout_ms / 1000, follow_redirects=False)
        ceas = _ceas or CeasSistem()
        http = Http(setari, self._client, ceas, _aleator or random.random)
        self.verificari = ClientVerificari(http, ceas)

    def close(self) -> None:
        """Inchide conexiunile clientului httpx construit de SDK (nu si pe cel injectat)."""
        if self._client_propriu:
            self._client.close()

    def __enter__(self) -> VerificRca:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
