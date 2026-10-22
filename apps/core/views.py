from urllib.parse import urlencode
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponse
from django.conf import settings
from apps.events.models import Event, FilterRule, RegistrationAttempt, UniCACredentials
from apps.scraping.models import ScanLog

def home_view(request):
    if not request.user.is_authenticated:
        return render(request, 'core/landing.html')

    user = request.user
    rules_count = user.filter_rules.count()
    active_channels = user.notification_preferences.filter(is_active=True).count()
    has_creds = hasattr(user, 'unica_credentials') and bool(user.unica_credentials.unica_identifier)
    auto_consent = hasattr(user, 'unica_credentials') and user.unica_credentials.auto_registration_consent

    latest_events = Event.objects.filter(is_simulated=False).order_by('-first_detected_at')[:6]
    total_events = Event.objects.filter(is_simulated=False).count()
    latest_scan = ScanLog.objects.order_by('-timestamp').first()
    recent_attempts = RegistrationAttempt.objects.filter(user=user).order_by('-timestamp')[:5]

    context = {
        'rules_count': rules_count,
        'active_channels': active_channels,
        'has_creds': has_creds,
        'auto_consent': auto_consent,
        'latest_events': latest_events,
        'total_events': total_events,
        'latest_scan': latest_scan,
        'recent_attempts': recent_attempts,
    }
    return render(request, 'core/dashboard.html', context)


def service_worker_view(request):
    return render(request, 'service-worker.js', content_type='application/javascript')


def manifest_view(request):
    return render(request, 'manifest.json', content_type='application/manifest+json')


def admin_login_view(request):
    next_url = request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = reverse('admin:index')
    if not request.user.is_authenticated:
        return redirect(f"{reverse('account_login')}?{urlencode({'next': next_url})}")
    if not request.user.is_staff:
        raise PermissionDenied
    return redirect(next_url)
