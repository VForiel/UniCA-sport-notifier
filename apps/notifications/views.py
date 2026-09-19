import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import NotificationPreference, PushSubscription

@login_required
def preferences_view(request):
    user = request.user
    channels = ['email', 'discord_webhook', 'telegram', 'whatsapp', 'push']
    prefs = {p.channel: p for p in user.notification_preferences.all()}

    if request.method == 'POST':
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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def simulate_test_notification_view(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("Méthode POST requise.")

    import time
    import uuid
    from apps.events.models import Event
    from apps.scraping.parsers import calculate_event_hash
    from apps.notifications.tasks import BACKENDS_MAP

    user = request.user
    source_id = f"sim_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    title = request.POST.get('title', 'KAYAK & Calanques [TEST SIMULATION]').strip()
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

    summary = " • ".join(results)
    messages.info(request, f"Simulation envoyée pour '{event.title}' ! Résultat des canaux : {summary}")

    if request.headers.get('HX-Request'):
        return render(request, 'notifications/partials/test_result.html', {
            'event': event,
            'results': results,
        })

    next_url = request.POST.get('next', 'notification_preferences')
    return redirect(next_url)

