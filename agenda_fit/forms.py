from django import forms
from .models import ConfiguracaoIntegracao

class IntegracaoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoIntegracao
        fields = ['totalpass_token', 'totalpass_ativo']
        widgets = {
            'totalpass_token': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cole o token aqui'}),
        }