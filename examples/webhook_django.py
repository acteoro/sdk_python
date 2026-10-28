"""Webhook-uri in Django. Adauga view-ul in urls.py: path("webhooks/acteo", notificare)."""

import os

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from acteo import Acteo, EroareWebhook, WebhookDocumentExpira

acteo = Acteo()  # cheia API din ACTEO_API_KEY; webhook-urile nu fac cereri pe retea


@csrf_exempt
@require_POST
def notificare(request: HttpRequest) -> HttpResponse:
    try:
        ev = acteo.webhooks.verifica_notificare(request.body, request.headers, os.environ["ACTEO_WEBHOOK_KEY"])
    except EroareWebhook as e:
        return JsonResponse({"error": e.cod}, status=400)
    if isinstance(ev, WebhookDocumentExpira):
        pass  # ex: trimite un email echipei de flota
    return JsonResponse({"ok": True})
