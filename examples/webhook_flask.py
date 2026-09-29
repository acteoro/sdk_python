"""Webhook-uri in Flask. Ruleaza: flask --app examples.webhook_flask run"""

import os

from flask import Flask, jsonify, request

from verificrca import EroareWebhook, WebhookDocumentExpira, verifica_webhook_notificare

app = Flask(__name__)


@app.post("/webhooks/verificrca")
def notificare():  # type: ignore[no-untyped-def]
    try:
        ev = verifica_webhook_notificare(request.get_data(), request.headers, os.environ["VERIFICRCA_WEBHOOK_KEY"])
    except EroareWebhook as e:
        return jsonify(error=e.cod), 400
    if isinstance(ev, WebhookDocumentExpira):
        app.logger.info("%s: %s expira in %s zile", ev.vehicul.numar_inmatriculare, ev.document.value, ev.zile_ramase)
    return jsonify(ok=True)
