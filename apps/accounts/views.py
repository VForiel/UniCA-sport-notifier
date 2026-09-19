from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout
from .models import AuditLog

@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})

@login_required
def delete_account_view(request):
    if request.method == 'POST':
        user = request.user
        email = user.email
        AuditLog.objects.create(
            user=None,
            action='ACCOUNT_DELETION',
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f"Suppression du compte par l'utilisateur lui-même : {email}"
        )
        logout(request)
        user.delete()
        messages.success(request, "Votre compte et l'ensemble de vos données ont été définitivement supprimés.")
        return redirect('account_login')
    return render(request, 'accounts/delete_confirm.html')
