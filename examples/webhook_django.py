"""Webhook-uri in Django. Adauga view-ul in urls.py: path("webhooks/verificrca", notificare)."""

import os

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from verificrca import EroareWebhook, WebhookDocumentExpira, verifica_webhook_notificare


@csrf_exempt
@require_POST
def notificare(request: HttpRequest) -> HttpResponse:
    try:
        ev = verifica_webhook_notificare(request.body, request.headers, os.environ["VERIFICRCA_WEBHOOK_KEY"])
    except EroareWebhook as e:
        return JsonResponse({"error": e.cod}, status=400)
    if isinstance(ev, WebhookDocumentExpira):
        pass  # ex: trimite un email echipei de flota
    return JsonResponse({"ok": True})
