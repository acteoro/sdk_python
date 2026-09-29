"""Adauga vehicule in monitorizare si afiseaza ce expira in urmatoarele 30 de zile."""

from contextlib import suppress
from datetime import datetime, timedelta, timezone

from verificrca import EroareConflict, VerificRca

with VerificRca() as vrca:
    for numar in ("B123ABC", "CJ45XYZ"):
        with suppress(EroareConflict):  # e deja in cont
            vrca.vehicule.adauga(numar_inmatriculare=numar)

    prag = datetime.now(timezone.utc) + timedelta(days=30)
    for v in vrca.vehicule.lista():
        for document, data in (
            ("RCA", v.rca_expira_la),
            ("ITP", v.itp_expira_la),
            ("Rovinieta", v.rovinieta_expira_la),
        ):
            if data and data <= prag:
                print(f"{v.numar_inmatriculare or v.serie_sasiu}: {document} expira la {data:%d.%m.%Y}")
