from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import FilterRule, UniCACredentials, Event, RegistrationAttempt
from .forms import FilterRuleForm, UniCACredentialsForm
from .services import encrypt_password, evaluate_event_for_user

@login_required
def rules_view(request):
    rules = request.user.filter_rules.all()
    if request.method == 'POST':
        form = FilterRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.user = request.user
            rule.save()
            messages.success(request, f"Règle '{rule.keyword}' ajoutée avec succès.")
            if request.headers.get('HX-Request'):
                return render(request, 'events/partials/rule_item.html', {'rule': rule})
            return redirect('rules_list')
    else:
        form = FilterRuleForm()

    return render(request, 'events/rules.html', {
        'form': form,
        'rules': rules,
    })


@login_required
def delete_rule_view(request, rule_id):
    rule = get_object_or_404(FilterRule, id=rule_id, user=request.user)
    keyword = rule.keyword
    rule.delete()
    if request.headers.get('HX-Request'):
        return HttpResponse("")
    messages.success(request, f"Règle '{keyword}' supprimée.")
    return redirect('rules_list')


@login_required
def credentials_view(request):
    credentials, _ = UniCACredentials.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UniCACredentialsForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('clear_credentials'):
                credentials.unica_identifier = ""
                credentials.encrypted_password = ""
                credentials.auto_registration_consent = False
                credentials.save()
                messages.success(request, "Vos identifiants UniCA ont été supprimés.")
                return redirect('credentials_settings')

            identifier = form.cleaned_data.get('unica_identifier')
            raw_password = form.cleaned_data.get('raw_password')
            consent = form.cleaned_data.get('auto_registration_consent')

            if identifier:
                credentials.unica_identifier = identifier
            if raw_password:
                credentials.encrypted_password = encrypt_password(raw_password)
            credentials.auto_registration_consent = consent
            credentials.save()

            messages.success(request, "Identifiants UniCA mis à jour avec succès (chiffrés avec Fernet).")
            return redirect('credentials_settings')
    else:
        initial = {
            'unica_identifier': credentials.unica_identifier,
            'auto_registration_consent': credentials.auto_registration_consent,
        }
        form = UniCACredentialsForm(initial=initial)

    return render(request, 'events/credentials.html', {
        'form': form,
        'credentials': credentials,
        'has_credentials': bool(credentials.unica_identifier and credentials.encrypted_password),
    })


@login_required
def recent_events_view(request):
    events = Event.objects.filter(is_simulated=False).order_by('-first_detected_at')[:50]
    evaluated_events = []
    for event in events:
        evaluation = evaluate_event_for_user(request.user, event)
        attempt = RegistrationAttempt.objects.filter(user=request.user, event=event).first()
        evaluated_events.append({
            'event': event,
            'evaluation': evaluation,
            'attempt': attempt,
        })

    return render(request, 'events/recent_events.html', {
        'evaluated_events': evaluated_events,
    })
