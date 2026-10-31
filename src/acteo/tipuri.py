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
    - `not_found`: sursa nu a gasit vehiculul.
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
