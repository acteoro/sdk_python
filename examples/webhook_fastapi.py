"""Webhook-uri in FastAPI. Ruleaza: uvicorn examples.webhook_fastapi:app"""

import os

from fastapi import FastAPI, HTTPException, Request

from acteo import Acteo, EroareWebhook, WebhookDocumentExpira

app = FastAPI()
acteo = Acteo()  # cheia API din ACTEO_API_KEY; webhook-urile nu fac cereri pe retea
CHEIE_WEBHOOK = os.environ["ACTEO_WEBHOOK_KEY"]


# URL-ul de webhook din dashboard: notificarile de expirare.
@app.post("/webhooks/acteo")
async def notificare(request: Request) -> dict[str, bool]:
    try:
        ev = acteo.webhooks.verifica_notificare(await request.body(), request.headers, CHEIE_WEBHOOK)
    except EroareWebhook as e:
        raise HTTPException(status_code=401 if e.cod in ("CHEIE_INVALIDA", "CHEIE_NECONFIGURATA") else 400) from e
    if isinstance(ev, WebhookDocumentExpira):
        print(f"{ev.vehicul.numar_inmatriculare}: {ev.document.value} expira in {ev.zile_ramase} zile")
    return {"ok": True}


# callback_url trimis la porneste(): HTTPS, cu un token secret in cale.
@app.post("/webhooks/acteo/rezultat/9f3k2x")
async def rezultat(request: Request) -> dict[str, bool]:
    r = acteo.webhooks.parseaza_rezultat(await request.body())
    print(r.request_id, r.status.value, r.result.expires_at if r.result else r.error)
    return {"ok": True}
