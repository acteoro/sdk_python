"""Webhook-uri in Flask. Ruleaza: flask --app examples.webhook_flask run"""

import os

from flask import Flask, jsonify, request

from acteo import Acteo, EroareWebhook, WebhookDocumentExpira

app = Flask(__name__)
acteo = Acteo()  # cheia API din ACTEO_API_KEY; webhook-urile nu fac cereri pe retea


@app.post("/webhooks/acteo")
def notificare():  # type: ignore[no-untyped-def]
    try:
        ev = acteo.webhooks.verifica_notificare(request.get_data(), request.headers, os.environ["ACTEO_WEBHOOK_KEY"])
    except EroareWebhook as e:
        return jsonify(error=e.cod), 400
    if isinstance(ev, WebhookDocumentExpira):
        app.logger.info("%s: %s expira in %s zile", ev.vehicul.numar_inmatriculare, ev.document.value, ev.zile_ramase)
    return jsonify(ok=True)
