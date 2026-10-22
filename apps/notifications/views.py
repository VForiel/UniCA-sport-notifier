import json
import logging
import re
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from .models import NotificationPreference, PushSubscription

logger = logging.getLogger(__name__)

# Seules les URL de webhook Discord sont acceptées : le serveur ne doit pas pouvoir être dirigé
# vers une adresse arbitraire (réseau Docker interne compris).
DISCORD_WEBHOOK_RE = re.compile(r'^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$')
DISCORD_USER_ID_RE = re.compile(r'^\d{15,25}$')
TELEGRAM_CHAT_ID_RE = re.compile(r'^(-?\d{1,20}|@\w{4,64})$')
PHONE_RE = re.compile(r'^\+?\d{8,15}$')
PING_MODES = {'none', 'favorite_only', 'all'}


def validate_channel_inputs(post):
    """Retourne la liste des erreurs de saisie des canaux (champs vides acceptés)."""
    errors = []
    discord_url = post.get('discord_webhook_url', '').strip()
    if discord_url and not DISCORD_WEBHOOK_RE.match(discord_url):
        errors.append("L'URL du webhook Discord doit être de la forme https://discord.com/api/webhooks/…")
    discord_user_id = post.get('discord_user_id', '').strip()
    if discord_user_id and not DISCORD_USER_ID_RE.match(discord_user_id):
        errors.append("L'identifiant utilisateur Discord ne doit contenir que des chiffres.")
    if post.get('discord_ping_mode', 'none') not in PING_MODES:
        errors.append("Mode de mention Discord inconnu.")
    chat_id = post.get('telegram_chat_id', '').strip()
    if chat_id and not TELEGRAM_CHAT_ID_RE.match(chat_id):
        errors.append("Le Chat ID Telegram doit être un nombre (ou @nom_de_canal).")
    phone = post.get('whatsapp_phone', '').strip().replace(' ', '').replace('-', '')
    if phone and not PHONE_RE.match(phone):
        errors.append("Le numéro WhatsApp doit être au format international (ex : +33612345678).")
    return errors

@login_required
def preferences_view(request):
    user = request.user
    channels = ['email', 'discord_webhook', 'telegram', 'whatsapp', 'push']
    prefs = {p.channel: p for p in user.notification_preferences.all()}

    if request.method == 'POST':
        errors = validate_channel_inputs(request.POST)
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('notification_preferences')

        # Traitement Email
        email_active = bool(request.POST.get('email_active'))
        pref_email, _ = NotificationPreference.objects.get_or_create(user=user, channel='email')
        pref_email.is_active = email_active
        pref_email.save()

        # Traitement Discord
        discord_active = bool(request.POST.get('discord_active'))
        discord_url = request.POST.get('discord_webhook_url', '').strip()
        discord_user_id = request.POST.get('discord_user_id', '').strip()
        discord_ping_mode = request.POST.get('discord_ping_mode', 'none').strip()
        pref_discord, _ = NotificationPreference.objects.get_or_create(user=user, channel='discord_webhook')
        pref_discord.is_active = discord_active
        pref_discord.config = {
            'webhook_url': discord_url,
            'discord_user_id': discord_user_id,
            'discord_ping_mode': discord_ping_mode,
        }
        pref_discord.save()

        # Traitement Telegram
        telegram_active = bool(request.POST.get('telegram_active'))
        telegram_chat_id = request.POST.get('telegram_chat_id', '').strip()
        pref_tg, _ = NotificationPreference.objects.get_or_create(user=user, channel='telegram')
        pref_tg.is_active = telegram_active
        pref_tg.config = {'chat_id': telegram_chat_id}
        pref_tg.save()

        # Traitement WhatsApp
        whatsapp_active = bool(request.POST.get('whatsapp_active'))
        whatsapp_phone = request.POST.get('whatsapp_phone', '').strip()
        pref_wa, _ = NotificationPreference.objects.get_or_create(user=user, channel='whatsapp')
        pref_wa.is_active = whatsapp_active
        pref_wa.config = {'phone_number': whatsapp_phone}
        pref_wa.save()

        messages.success(request, "Vos préférences de notification ont été enregistrées.")
        return redirect('notification_preferences')

    push_sub_count = user.push_subscriptions.count()

    context = {
        'pref_email': prefs.get('email'),
        'pref_discord': prefs.get('discord_webhook'),
        'pref_telegram': prefs.get('telegram'),
        'pref_whatsapp': prefs.get('whatsapp'),
        'pref_push': prefs.get('push'),
        'push_sub_count': push_sub_count,
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    }
    return render(request, 'notifications/preferences.html', context)


@login_required
def push_vapid_key_view(request):
    public_key = getattr(settings, 'VAPID_PUBLIC_KEY', '')
    return JsonResponse({'publicKey': public_key})


@login_required
def push_subscribe_view(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("Méthode non autorisée")

    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')

        if not endpoint or not p256dh or not auth:
            return JsonResponse({'error': 'Données de souscription incomplètes'}, status=400)

        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user,
                'p256dh': p256dh,
                'auth': auth,
            }
        )

        # Activer automatiquement la préférence push
        pref_push, _ = NotificationPreference.objects.get_or_create(user=request.user, channel='push')
        pref_push.is_active = True
        pref_push.save()

        return JsonResponse({'status': 'success', 'message': 'Abonnement Push enregistré'})
    except (ValueError, AttributeError):
        return JsonResponse({'error': 'Données de souscription invalides'}, status=400)
    except Exception:
        logger.exception("Enregistrement d'un abonnement Push impossible")
        return JsonResponse({'error': "Erreur serveur lors de l'enregistrement"}, status=500)


@login_required
@require_POST
@ratelimit(key='user', rate='5/h', block=False)
def simulate_test_notification_view(request):
    if getattr(request, 'limited', False):
        messages.error(request, "Trop de tests envoyés : réessayez dans une heure.")
        if request.headers.get('HX-Request'):
            return render(request, 'notifications/partials/test_result.html', {
                'results': ["Limite atteinte : 5 tests par heure."],
            })
        return redirect('notification_preferences')

    import time
    import uuid
    from apps.events.models import Event
    from apps.scraping.parsers import calculate_event_hash
    from apps.notifications.tasks import BACKENDS_MAP

    user = request.user
    source_id = f"sim_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    title = 'KAYAK & Calanques [TEST SIMULATION]'
    event_type = 'Sortie'
    date_event = 'Demain 10:00 - 17:00'
    location = 'Base Nautique Valrose'
    desc = (
        "Ceci est un événement de TEST simulé pour vérifier le bon fonctionnement "
        "de vos canaux de notification (Push Web, Discord, Telegram, WhatsApp, Email)."
    )

    content_hash = calculate_event_hash(source_id, title, event_type, date_event, location, desc)
    event = Event.objects.create(
        source_id=source_id,
        title=title,
        event_type=event_type,
        date_event=date_event,
        location=location,
        supervisor="Simulateur de test",
        description=desc,
        url=f"https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement#event-{source_id}",
        image_url="https://sport.univ-cotedazur.fr/media/cache/thumb_large_big/upload/public/image/6a17e6307f445452066731.png",
        is_simulated=True,
        content_hash=content_hash,
    )

    active_prefs = user.notification_preferences.filter(is_active=True)
    results = []

    if not active_prefs.exists():
        backend = BACKENDS_MAP['email']()
        ok = backend.send(user, event, f"🔔 [TEST SIMULATION] {title}")
        results.append(f"Email ({user.email}) : {'Envoyé' if ok else 'Erreur SMTP'}")
    else:
        for pref in active_prefs:
            backend_cls = BACKENDS_MAP.get(pref.channel)
            if backend_cls:
                backend = backend_cls()
                ok = backend.send(user, event, f"🔔 [TEST SIMULATION] {title}")
                status = "Envoyé avec succès" if ok else "Échec / Configuration incomplète"
                results.append(f"{pref.get_channel_display()} : {status}")

    # L'événement fictif n'a servi qu'à construire les messages
    event_title = event.title
    event.delete()

    summary = " • ".join(results)
    if request.headers.get('HX-Request'):
        return render(request, 'notifications/partials/test_result.html', {
            'title': event_title,
            'results': results,
        })

    messages.info(request, f"Test envoyé. Résultat des canaux : {summary}")
    return redirect('notification_preferences')

