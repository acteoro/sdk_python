"""Clientul `Acteo` (sincron), organizat pe domeniu si document: `acteo.auto.rca.verifica("B123ABC")`."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import httpx

from ._intern import documente
from ._intern.ceas import Ceas
from ._intern.setari import PROFIL_ACTEO, SetariRetry
from ._intern.verificari import INTERVAL_IMPLICIT_MS, TIMEOUT_IMPLICIT_MS
from .client import ClientVehicule, ClientVerificari, _ClientSincron
from .modele import (
    RezultatArr,
    RezultatItp,
    RezultatRca,
    RezultatRovinieta,
    VerificareInCurs,
    VerificareInCursArr,
    VerificareInCursItp,
    VerificareInCursRca,
    VerificareInCursRovinieta,
    WebhookDocumentExpira,
    WebhookRezultat,
    WebhookTest,
)
from .webhooks import Corp, parseaza_webhook_rezultat, verifica_webhook_notificare


class ClientRca:
    """Asigurarea RCA, din baza AIDA. Il accesezi prin `acteo.auto.rca`.

    Identificatorul: un text (17 caractere fara I, O si Q = VIN, altfel numar de inmatriculare)
    sau `numar=` si `vin=`; cu amandoua, cautarea in AIDA e mai exacta.
    `verifica()` si `porneste()` consuma din cota; `rezultat()` si `asteapta()` sunt gratuite.
    """

    def __init__(self, verificari: ClientVerificari) -> None:
        self._v = verificari

    def verifica(
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
        return self._v._verifica_si_asteapta(tinta, interval_ms, timeout_ms, documente.MODELE_RCA)

    def porneste(
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
        return self._v._porneste(tinta, documente.MODELE_RCA)

    def rezultat(
        self,
        referinta: VerificareInCurs | str | None = None,
        /,
        *,
        numar: str | None = None,
        vin: str | None = None,
    ) -> RezultatRca | VerificareInCursRca:
        """Interogheaza o singura data rezultatul, dupa verificarea in curs sau identificator. Gratuit."""
        ref = documente.referinta_rca(referinta, numar, vin)
        return self._v._interogheaza(ref, None, documente.MODELE_RCA)

    def asteapta(
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
        return self._v._asteapta(ref, interval_ms, timeout_ms, documente.MODELE_RCA)


class ClientItp:
    """Inspectia tehnica periodica, din RAR. Il accesezi prin `acteo.auto.itp`. Cere VIN-ul."""

    def __init__(self, verificari: ClientVerificari) -> None:
        self._v = verificari

    def verifica(
        self, vin: str, *, interval_ms: float = INTERVAL_IMPLICIT_MS, timeout_ms: float = TIMEOUT_IMPLICIT_MS
    ) -> RezultatItp:
        """Verifica ITP-ul si asteapta rezultatul final de la sursa oficiala."""
        tinta = documente.tinta_itp(vin, None)
        return self._v._verifica_si_asteapta(tinta, interval_ms, timeout_ms, documente.MODELE_ITP)

    def porneste(self, vin: str, *, callback_url: str | None = None) -> RezultatItp | VerificareInCursItp:
        """Porneste verificarea fara sa astepte: rezultatul final sau `status == "processing"`."""
        return self._v._porneste(documente.tinta_itp(vin, callback_url), documente.MODELE_ITP)

    def rezultat(self, referinta: VerificareInCurs | str, /) -> RezultatItp | VerificareInCursItp:
        """Interogheaza o singura data rezultatul, dupa verificarea in curs sau VIN. Gratuit."""
        return self._v._interogheaza(documente.referinta_itp(referinta), None, documente.MODELE_ITP)

    def asteapta(
        self,
        referinta: VerificareInCurs | str,
        /,
        *,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> RezultatItp:
        """Interogheaza periodic pana la rezultatul final. Gratuit."""
        ref = documente.referinta_itp(referinta)
        return self._v._asteapta(ref, interval_ms, timeout_ms, documente.MODELE_ITP)


class ClientRovinieta:
    """Rovinieta, din CNAIR. Il accesezi prin `acteo.auto.rovinieta`.

    Cere numarul de inmatriculare, VIN-ul si numarul certificatului de inmatriculare (talon).
    """

    def __init__(self, verificari: ClientVerificari) -> None:
        self._v = verificari

    def verifica(
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
        return self._v._verifica_si_asteapta(tinta, interval_ms, timeout_ms, documente.MODELE_ROVINIETA)

    def porneste(
        self, *, numar: str, vin: str, serie_talon: str, callback_url: str | None = None
    ) -> RezultatRovinieta | VerificareInCursRovinieta:
        """Porneste verificarea fara sa astepte: rezultatul final sau `status == "processing"`."""
        tinta = documente.tinta_rovinieta(numar, vin, serie_talon, callback_url)
        return self._v._porneste(tinta, documente.MODELE_ROVINIETA)

    def rezultat(
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
        return self._v._interogheaza(ref, None, documente.MODELE_ROVINIETA)

    def asteapta(
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
        return self._v._asteapta(ref, interval_ms, timeout_ms, documente.MODELE_ROVINIETA)


class ClientArr:
    """Copia conforma ARR. Il accesezi prin `acteo.auto.arr`. Cere numarul de inmatriculare."""

    def __init__(self, verificari: ClientVerificari) -> None:
        self._v = verificari

    def verifica(
        self, numar: str, *, interval_ms: float = INTERVAL_IMPLICIT_MS, timeout_ms: float = TIMEOUT_IMPLICIT_MS
    ) -> RezultatArr:
        """Verifica copia conforma ARR si asteapta rezultatul final de la sursa oficiala."""
        tinta = documente.tinta_arr(numar, None)
        return self._v._verifica_si_asteapta(tinta, interval_ms, timeout_ms, documente.MODELE_ARR)

    def porneste(self, numar: str, *, callback_url: str | None = None) -> RezultatArr | VerificareInCursArr:
        """Porneste verificarea fara sa astepte: rezultatul final sau `status == "processing"`."""
        return self._v._porneste(documente.tinta_arr(numar, callback_url), documente.MODELE_ARR)

    def rezultat(self, referinta: VerificareInCurs | str, /) -> RezultatArr | VerificareInCursArr:
        """Interogheaza o singura data rezultatul, dupa verificarea in curs sau numar. Gratuit."""
        return self._v._interogheaza(documente.referinta_arr(referinta), None, documente.MODELE_ARR)

    def asteapta(
        self,
        referinta: VerificareInCurs | str,
        /,
        *,
        interval_ms: float = INTERVAL_IMPLICIT_MS,
        timeout_ms: float = TIMEOUT_IMPLICIT_MS,
    ) -> RezultatArr:
        """Interogheaza periodic pana la rezultatul final. Gratuit."""
        ref = documente.referinta_arr(referinta)
        return self._v._asteapta(ref, interval_ms, timeout_ms, documente.MODELE_ARR)


class ClientAuto:
    """Domeniul auto: documentele unei masini (RCA, ITP, rovinieta, ARR) si flota din cont."""

    def __init__(self, verificari: ClientVerificari, vehicule: ClientVehicule) -> None:
        self.rca = ClientRca(verificari)
        """Asigurarea RCA: `acteo.auto.rca.verifica("B123ABC")`."""
        self.itp = ClientItp(verificari)
        """ITP: `acteo.auto.itp.verifica("WVWZZZ1JZXW000001")`."""
        self.rovinieta = ClientRovinieta(verificari)
        """Rovinieta: `acteo.auto.rovinieta.verifica(numar=..., vin=..., serie_talon=...)`."""
        self.arr = ClientArr(verificari)
        """Copia conforma ARR: `acteo.auto.arr.verifica("B123ABC")`."""
        self.flota = vehicule
        """Vehiculele monitorizate din cont: `lista()`, `adauga()`, `sterge()`."""


class ClientWebhooks:
    """Citirea webhook-urilor trimise de API. Nu face cereri pe retea, deci merge si in cod async."""

    def parseaza_rezultat(self, corp: Corp) -> WebhookRezultat:
        """Citeste rezultatul trimis la `callback_url`. Arunca `EroareWebhook`."""
        return parseaza_webhook_rezultat(corp)

    def verifica_notificare(self, corp: Corp, headere: Any, cheie: str) -> WebhookDocumentExpira | WebhookTest:
        """Verifica cheia si citeste o notificare `document.expira` sau `webhook.test`. Arunca `EroareWebhook`."""
        return verifica_webhook_notificare(corp, headere, cheie)


class Acteo(_ClientSincron):
    """Clientul sincron al API-ului Acteo, organizat pe domenii.

    >>> with Acteo() as acteo:  # cheia din ACTEO_API_KEY
    ...     rca = acteo.auto.rca.verifica("B123ABC")

    `acteo.auto.rca`, `.itp`, `.rovinieta`, `.arr`, `acteo.auto.flota` si `acteo.webhooks`.
    Cheia vine din `api_key`, altfel din `ACTEO_API_KEY`, apoi din `VERIFICRCA_API_KEY`.
    `http_client` permite un `httpx.Client` propriu; SDK-ul nu il inchide. Constructorul nu
    face cereri pe retea.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_ms: float = 30_000,
        retry: SetariRetry | Mapping[str, int] | bool | None = None,
        http_client: httpx.Client | None = None,
        user_agent: str | None = None,
        _ceas: Ceas | None = None,
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
        self.auto = ClientAuto(ClientVerificari(self._http, self._ceas), ClientVehicule(self._http))
        """Documentele unei masini si flota."""
        self.webhooks = ClientWebhooks()
        """Citirea webhook-urilor."""
