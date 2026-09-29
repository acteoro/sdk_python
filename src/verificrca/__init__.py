"""SDK Python oficial pentru API-ul verificrca.ro: verificare RCA, ITP, rovinieta si ARR."""

from ._versiune import URL_IMPLICIT, VERSIUNE_SDK, __version__
from .erori import (
    EroareAutentificare,
    EroareConfigurare,
    EroareConflict,
    EroareHttp,
    EroareInterzis,
    EroareLimita,
    EroareNegasit,
    EroarePlanInactiv,
    EroareRaspunsInvalid,
    EroareRetea,
    EroareServer,
    EroareTimeoutVerificare,
    EroareValidare,
    EroareVerificare,
    EroareWebhook,
    VerificRcaError,
)
from .tipuri import StatusDocument, StatusWebhook, TipVerificare
from .validare import TIPURI_VERIFICARE, este_numar_inmatriculare_valid, este_vin_valid, normalizeaza

__all__ = [
    "TIPURI_VERIFICARE",
    "URL_IMPLICIT",
    "VERSIUNE_SDK",
    "EroareAutentificare",
    "EroareConfigurare",
    "EroareConflict",
    "EroareHttp",
    "EroareInterzis",
    "EroareLimita",
    "EroareNegasit",
    "EroarePlanInactiv",
    "EroareRaspunsInvalid",
    "EroareRetea",
    "EroareServer",
    "EroareTimeoutVerificare",
    "EroareValidare",
    "EroareVerificare",
    "EroareWebhook",
    "StatusDocument",
    "StatusWebhook",
    "TipVerificare",
    "VerificRcaError",
    "__version__",
    "este_numar_inmatriculare_valid",
    "este_vin_valid",
    "normalizeaza",
]
