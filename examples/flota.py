"""Adauga vehicule in monitorizare si afiseaza ce RCA, ITP, rovinieta sau ARR expira in 30 de zile."""

from contextlib import suppress
from datetime import datetime, timedelta, timezone

from acteo import Acteo, EroareConflict

with Acteo() as acteo:
    for numar in ("B123ABC", "CJ45XYZ"):
        with suppress(EroareConflict):  # e deja in cont
            acteo.auto.flota.adauga(numar_inmatriculare=numar)

    prag = datetime.now(timezone.utc) + timedelta(days=30)
    for v in acteo.auto.flota.lista():
        for document, data in (
            ("RCA", v.rca_expira_la),
            ("ITP", v.itp_expira_la),
            ("Rovinieta", v.rovinieta_expira_la),
            ("ARR", v.arr_expira_la),
        ):
            if data and data <= prag:
                print(f"{v.numar_inmatriculare or v.serie_sasiu}: {document} expira la {data:%d.%m.%Y}")
        if v.serie_talon_respinsa:
            print(f"{v.numar_inmatriculare}: numarul talonului a fost respins, rovinieta nu se mai verifica.")
