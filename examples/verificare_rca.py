"""Verifica RCA-ul unei masini dupa numar si, optional, dupa VIN.

Ruleaza: ACTEO_API_KEY=... python examples/verificare_rca.py B123ABC [VIN]
"""

import sys

from acteo import Acteo, EroareLimita, EroareValidare

numar = sys.argv[1] if len(sys.argv) > 1 else "B123ABC"
vin = sys.argv[2] if len(sys.argv) > 2 else None

with Acteo() as acteo:
    try:
        r = acteo.auto.rca.verifica(numar=numar, vin=vin)
    except EroareValidare as e:
        sys.exit(f"Date invalide: {e.mesaj}")
    except EroareLimita as e:
        sys.exit(f"Limita atinsa ({e.cod}): {e.mesaj}")

print(
    f"RCA {r.query}: {r.status.value}, expira la {r.expires_at:%d.%m.%Y}"
    if r.expires_at
    else f"RCA {r.query}: {r.status.value}"
)
if r.limite:
    print(f"Verificari ramase azi: {r.limite.zi.ramase}")
