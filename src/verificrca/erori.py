"""Erorile SDK-ului. `except VerificRcaError` prinde orice eroare de la verificrca."""

from __future__ import annotations


class VerificRcaError(Exception):
    """Baza tuturor erorilor SDK-ului.

    Atribute: `mesaj` (in romana, exact cum vine de la API cand exista), `status` (HTTP),
    `cod` (ex: `LIMIT_ATINS`, `VEHICUL_EXISTENT`), `hint` (cum se rezolva), `raspuns`
    (corpul brut, pentru depanare). Eroarea originala, cand exista, e in `__cause__`.
    """

    def __init__(
        self,
        mesaj: str,
        *,
        status: int | None = None,
        cod: str | None = None,
        hint: str | None = None,
        raspuns: object = None,
    ) -> None:
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.status = status
        self.cod = cod
        self.hint = hint
        self.raspuns = raspuns

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.mesaj!r}, status={self.status!r}, cod={self.cod!r})"


class EroareConfigurare(VerificRcaError):
    """Optiunile clientului sunt invalide (cheie API lipsa, URL gresit etc.)."""


class EroareValidare(VerificRcaError):
    """Datele trimise sunt invalide: local, inainte de orice cerere (nu consuma din cota), sau 400 de la API."""

    def __init__(
        self,
        mesaj: str,
        *,
        status: int | None = None,
        cod: str | None = None,
        hint: str | None = None,
        raspuns: object = None,
        acceptate: list[str] | None = None,
        camp: str | None = None,
    ) -> None:
        super().__init__(mesaj, status=status, cod=cod, hint=hint, raspuns=raspuns)
        self.acceptate = acceptate
        self.camp = camp


class EroareAutentificare(VerificRcaError):
    """401: cheia API lipseste, e invalida sau a fost dezactivata."""


class EroarePlanInactiv(VerificRcaError):
    """402: contul nu are un abonament activ pentru operatia ceruta."""


class EroareInterzis(VerificRcaError):
    """403: operatia nu e permisa pe planul curent (`LIMIT_ATINS`, `ARR_NECESITA_PLAN`)."""

    def __init__(
        self,
        mesaj: str,
        *,
        status: int | None = None,
        cod: str | None = None,
        hint: str | None = None,
        raspuns: object = None,
        limita: int | None = None,
    ) -> None:
        super().__init__(mesaj, status=status, cod=cod, hint=hint, raspuns=raspuns)
        self.limita = limita


class EroareNegasit(VerificRcaError):
    """404: resursa nu exista sau nu apartine contului cheii."""


class EroareConflict(VerificRcaError):
    """409: vehiculul exista deja in cont (`VEHICUL_EXISTENT`)."""


class EroareLimita(VerificRcaError):
    """429: limita a fost atinsa. `cod` spune care.

    - `COTA_ATINSA`: cota zilnica sau lunara de verificari a planului;
    - `LIMITA_FLOTA_ATINSA`: plafonul zilnic de adaugari/stergeri de vehicule;
    - `PREA_MULTE_CERERI`: polling prea des (SDK-ul reincearca singur).
    """

    def __init__(
        self,
        mesaj: str,
        *,
        status: int | None = None,
        cod: str | None = None,
        hint: str | None = None,
        raspuns: object = None,
        retry_after_ms: int | None = None,
        utilizare_zi: str | None = None,
        utilizare_luna: str | None = None,
    ) -> None:
        super().__init__(mesaj, status=status, cod=cod, hint=hint, raspuns=raspuns)
        self.retry_after_ms = retry_after_ms
        self.utilizare_zi = utilizare_zi
        self.utilizare_luna = utilizare_luna


class EroareServer(VerificRcaError):
    """5xx: eroare pe serverul verificrca. Cererile sigure se reincearca automat."""


class EroareHttp(VerificRcaError):
    """Orice alt status HTTP neasteptat (inclusiv redirecturi, care nu se urmeaza)."""


class EroareRetea(VerificRcaError):
    """Cererea nu a primit raspuns: retea cazuta, DNS, conexiune refuzata sau timeout.

    `timeout` e adevarat cand cererea a depasit timpul de raspuns. `neajunsa` e adevarat cand
    e sigur ca cererea nu a plecat spre server, deci se poate repeta fara risc chiar si un POST.
    """

    def __init__(
        self,
        mesaj: str,
        *,
        status: int | None = None,
        cod: str | None = None,
        hint: str | None = None,
        raspuns: object = None,
        timeout: bool = False,
        neajunsa: bool = False,
    ) -> None:
        super().__init__(mesaj, status=status, cod=cod, hint=hint, raspuns=raspuns)
        self.timeout = timeout
        self.neajunsa = neajunsa


class EroareRaspunsInvalid(VerificRcaError):
    """Raspunsul API-ului nu are forma asteptata (JSON invalid sau campuri lipsa)."""


class EroareVerificare(VerificRcaError):
    """Verificarea s-a incheiat cu `status: error`. `cod` e mereu `VERIFICARE_ESUATA`.

    `cod_sursa` spune de ce, cand sursa oficiala a refuzat datele trimise:
    `serie_talon_invalida`, `vin_invalid` sau `numar_invalid`. Atunci o reincercare cu aceleasi
    date nu ajuta; corecteaza campul respectiv. Cand `cod_sursa` e `None`, sursa nu a raspuns
    in timp util si verificarea poate fi reluata.
    """

    def __init__(
        self,
        mesaj: str,
        *,
        status: int | None = None,
        cod: str | None = None,
        hint: str | None = None,
        raspuns: object = None,
        cod_sursa: str | None = None,
    ) -> None:
        super().__init__(mesaj, status=status, cod=cod, hint=hint, raspuns=raspuns)
        self.cod_sursa = cod_sursa


class EroareTimeoutVerificare(VerificRcaError):
    """`asteapta` sau `verifica_si_asteapta` a depasit timpul maxim de asteptare."""


class EroareWebhook(VerificRcaError):
    """Un webhook primit nu poate fi acceptat: cheie gresita sau payload invalid."""
