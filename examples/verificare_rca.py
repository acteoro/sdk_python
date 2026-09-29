"""Verifica RCA-ul unei masini dupa numar.

Ruleaza: VERIFICRCA_API_KEY=vrca_... python examples/verificare_rca.py B123ABC
"""

import sys

from verificrca import EroareLimita, EroareValidare, VerificRca

numar = sys.argv[1] if len(sys.argv) > 1 else "B123ABC"

with VerificRca() as vrca:
    try:
        r = vrca.verificari.verifica_si_asteapta(tip="rca", query=numar)
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
