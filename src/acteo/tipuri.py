"""Enum-urile contractului public."""

from enum import Enum
from typing import Literal


class TipVerificare(str, Enum):
    """Tipul verificarii: RCA (AIDA/BAAR), ITP (RAR), rovinieta (CNAIR), ARR (copie conforma)."""

    RCA = "rca"
    ITP = "itp"
    ROVINIETA = "rovinieta"
    ARR = "arr"


class StatusDocument(str, Enum):
    """Starea documentului.

    - `valid`: valabil si departe de expirare;
    - `warning`: expira curand (RCA 14 zile, ITP 30, rovinieta 7, ARR 14);
    - `expired`: expirat sau inexistent, confirmat de sursa oficiala;
    - `not_found`: sursa nu a gasit vehiculul (`code == "NOT_FOUND"`).
    """

    VALID = "valid"
    WARNING = "warning"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"


class StatusWebhook(str, Enum):
    """Statusul din rezultatul livrat la `callback_url`: starea documentului sau `error`."""

    VALID = "valid"
    WARNING = "warning"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"
    ERROR = "error"


UnghiImagine = Literal["trei-sferturi", "fata", "profil", "spate", "trei-sferturi-dreapta", "profil-dreapta"]
"""Unghiul pozei unei masini. Implicit `"trei-sferturi"`."""

StatusImagine = Literal["gata", "in-lucru", "necunoscut", "indisponibil"]
"""Starea pozei unei masini.

- `gata`: poza masinii cerute (se taxeaza);
- `in-lucru`: poza se genereaza acum; cere din nou dupa `retry_after_ms`;
- `necunoscut`: marca sau modelul nu au fost identificate;
- `indisponibil`: generarea a esuat; se reincearca la prima cerere dupa 24h.

In afara de `gata`, primesti poza generica (masina sub husa), netaxata.
"""

StatusPolitaPad = Literal["processing", "done", "error"]
"""Starea unei verificari de polita PAD.

- `processing`: PADROM nu a raspuns inca; mai intreaba peste cateva secunde;
- `done`: PADROM a raspuns, verdictul e in `valabila`;
- `error`: PADROM a refuzat datele (`INVALID_IDENTIFIER`) sau nu a raspuns. Apare doar in webhook;
  `rezultat()` si `asteapta()` arunca `EroareVerificare`.
"""


class CodEroare(str, Enum):
    """Codurile stabile pe care API-ul le pune in `code`, in ordinea din documentatie.

    Fiind `str`, se compara direct cu `cod` de pe erori: `err.cod == CodEroare.DAILY_LIMIT_REACHED`.
    Primele opt sunt cele din contract:

    - `UPSTREAM_UNAVAILABLE`: sursa oficiala nu raspunde sau raspunde cu eroare;
    - `UPSTREAM_TIMEOUT`: sursa oficiala nu a raspuns in intervalul maxim;
    - `UPSTREAM_BLOCKED`: accesul la sursa oficiala e restrictionat temporar;
    - `UPSTREAM_CHANGED`: structura sursei s-a modificat, serviciul e in adaptare;
    - `DAILY_LIMIT_REACHED`: limita zilnica a planului, se reseteaza la miezul noptii (ora Romaniei);
    - `PLAN_LIMIT_REACHED`: limita lunara, sau plafonul consumului peste plan;
    - `NOT_FOUND`: identificatorul nu exista la sursa oficiala;
    - `INVALID_IDENTIFIER`: sursa oficiala a respins identificatorul ca invalid.

    Restul tin de un produs anume: `SOLD_INSUFICIENT`, `PLAFON_NETAXAT`, `OCUPAT`, `INDISPONIBIL`,
    `VIN_NEDECODAT`, `VIN_INVALID`, `ARR_NECESITA_PLAN`, `LIMIT_ATINS` (numarul de masini din plan),
    `VEHICUL_EXISTENT`, `NEGASIT`, `LIMITA_FLOTA_ATINSA`.

    `cod` de pe erori ramane `str`, ca un cod adaugat ulterior de API sa nu strice nimic.
    """

    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_BLOCKED = "UPSTREAM_BLOCKED"
    UPSTREAM_CHANGED = "UPSTREAM_CHANGED"
    DAILY_LIMIT_REACHED = "DAILY_LIMIT_REACHED"
    PLAN_LIMIT_REACHED = "PLAN_LIMIT_REACHED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    SOLD_INSUFICIENT = "SOLD_INSUFICIENT"
    PLAFON_NETAXAT = "PLAFON_NETAXAT"
    OCUPAT = "OCUPAT"
    INDISPONIBIL = "INDISPONIBIL"
    VIN_NEDECODAT = "VIN_NEDECODAT"
    VIN_INVALID = "VIN_INVALID"
    ARR_NECESITA_PLAN = "ARR_NECESITA_PLAN"
    LIMIT_ATINS = "LIMIT_ATINS"
    VEHICUL_EXISTENT = "VEHICUL_EXISTENT"
    NEGASIT = "NEGASIT"
    LIMITA_FLOTA_ATINSA = "LIMITA_FLOTA_ATINSA"


CODURI_EROARE: tuple[str, ...] = tuple(c.value for c in CodEroare)
"""Toate codurile din `CodEroare`, ca texte, in aceeasi ordine."""

CodEsecVerificare = Literal[
    "INVALID_IDENTIFIER", "UPSTREAM_UNAVAILABLE", "UPSTREAM_TIMEOUT", "UPSTREAM_BLOCKED", "UPSTREAM_CHANGED"
]
"""De ce s-a incheiat o verificare cu `status: "error"`.

- `INVALID_IDENTIFIER`: sursa a refuzat datele trimise; campul e in `cod_sursa`;
- `UPSTREAM_UNAVAILABLE`, `UPSTREAM_TIMEOUT`, `UPSTREAM_BLOCKED`, `UPSTREAM_CHANGED`: sursa oficiala nu a
  dat un raspuns; reia mai tarziu cu o cerere noua.
"""
