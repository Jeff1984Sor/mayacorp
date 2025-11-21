from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

class HorarioFixoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        
        # Conta quantos horários estão sendo salvos (ignorando os deletados)
        count = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                count += 1
        
        # Pega a instância do contrato (pai)
        contrato = self.instance
        
        # Valida
        if contrato.plano and count > contrato.plano.frequencia_semanal:
            raise ValidationError(f"O plano {contrato.plano.nome} permite apenas {contrato.plano.frequencia_semanal} horários por semana. Você selecionou {count}.")