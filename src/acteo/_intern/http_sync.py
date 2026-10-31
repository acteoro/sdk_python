"""Trimite cereri sincron prin httpx, cu retry si termen."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from ..erori import EroareLimita, EroareRetea, EroareServer, EroareTimeoutVerificare
from .ceas import Ceas
from .cereri import CerereHttp, pregateste
from .raspunsuri import Raspuns, construieste_raspuns
from .retry import pauza_ms, se_poate_reincerca
from .setari import Setari
from .transport import eroare_retea, timeout_cerere


class Http:
    def __init__(self, setari: Setari, client: httpx.Client, ceas: Ceas, aleator: Callable[[], float]) -> None:
        self._setari = setari
        self._client = client
        self._ceas = ceas
        self._aleator = aleator

    def trimite(self, cerere: CerereHttp, termen_ms: float | None = None) -> Raspuns:
        incercare = 0
        while True:
            try:
                return self._o_data(cerere)
            except (EroareRetea, EroareServer, EroareLimita) as e:
                retry = self._setari.retry
                if (
                    retry is None
                    or incercare >= retry.incercari
                    or not se_poate_reincerca(cerere.idempotenta, e, retry)
                ):
                    raise
                pauza = pauza_ms(retry, incercare, e, self._aleator)
                if termen_ms is not None and self._ceas.monoton_ms() + pauza >= termen_ms:
                    raise EroareTimeoutVerificare(
                        "Termenul de asteptare a expirat in timpul reincercarilor.", cod="TIMEOUT_VERIFICARE"
                    ) from e
                self._ceas.dormi_ms(pauza)
                incercare += 1

    def _o_data(self, cerere: CerereHttp) -> Raspuns:
        p = pregateste(self._setari, cerere)
        timeout = timeout_cerere(self._client.timeout, cerere.timeout_minim_ms)
        req = self._client.build_request(
            p.metoda,
            p.url,
            params=p.params,
            headers=p.headere,
            content=p.continut,
            timeout=httpx.USE_CLIENT_DEFAULT if timeout is None else timeout,
        )
        try:
            raspuns = self._client.send(req, follow_redirects=False)
        except httpx.RequestError as exc:
            raise eroare_retea(exc, cerere.metoda, cerere.cale) from exc
        headere = {k.lower(): v for k, v in raspuns.headers.items()}
        return construieste_raspuns(raspuns.status_code, headere, raspuns.content, self._ceas.acum_ms())
