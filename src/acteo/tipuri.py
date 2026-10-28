"""Enum-urile contractului public."""

from enum import Enum


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
