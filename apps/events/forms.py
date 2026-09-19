from django import forms
from .models import FilterRule, UniCACredentials

class FilterRuleForm(forms.ModelForm):
    class Meta:
        model = FilterRule
        fields = ['rule_type', 'match_mode', 'keyword', 'target_field', 'case_sensitive']
        widgets = {
            'keyword': forms.TextInput(attrs={'placeholder': 'Ex: Kayak, Volley, Tennis...'}),
        }


class UniCACredentialsForm(forms.Form):
    unica_identifier = forms.CharField(
        max_length=150,
        required=False,
        label="Identifiant UniCA",
        widget=forms.TextInput(attrs={'placeholder': 'prenom.nom@univ-cotedazur.fr ou login'})
    )
    raw_password = forms.CharField(
        max_length=255,
        required=False,
        label="Mot de passe UniCA",
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••••••'})
    )
    auto_registration_consent = forms.BooleanField(
        required=False,
        label="J'autorise l'application à tenter de réserver temporairement ma place (créneau 30 min) pour les événements favoris sans effectuer de paiement."
    )
    clear_credentials = forms.BooleanField(
        required=False,
        label="Supprimer mes identifiants enregistrés"
    )
