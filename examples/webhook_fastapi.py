"""Webhook-uri in FastAPI. Ruleaza: uvicorn examples.webhook_fastapi:app"""

import os

from fastapi import FastAPI, HTTPException, Request

from verificrca import EroareWebhook, WebhookDocumentExpira, parseaza_webhook_rezultat, verifica_webhook_notificare

app = FastAPI()
CHEIE_WEBHOOK = os.environ["VERIFICRCA_WEBHOOK_KEY"]


# URL-ul de webhook din dashboard: notificarile de expirare.
@app.post("/webhooks/verificrca")
async def notificare(request: Request) -> dict[str, bool]:
    try:
        ev = verifica_webhook_notificare(await request.body(), request.headers, CHEIE_WEBHOOK)
    except EroareWebhook as e:
        raise HTTPException(status_code=401 if e.cod in ("CHEIE_INVALIDA", "CHEIE_NECONFIGURATA") else 400) from e
    if isinstance(ev, WebhookDocumentExpira):
        print(f"{ev.vehicul.numar_inmatriculare}: {ev.document.value} expira in {ev.zile_ramase} zile")
    return {"ok": True}


# callback_url trimis la porneste(): HTTPS, cu un token secret in cale.
@app.post("/webhooks/verificrca/rezultat/9f3k2x")
async def rezultat(request: Request) -> dict[str, bool]:
    r = parseaza_webhook_rezultat(await request.body())
    print(r.request_id, r.status.value, r.result.expires_at if r.result else r.error)
    return {"ok": True}
