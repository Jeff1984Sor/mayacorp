
# Register your models here.
from django.contrib import admin
from .models import TemplateContrato, Plano, Contrato, HorarioFixo
from .forms import HorarioFixoFormSet # <--- Importe o Form
from agenda_fit.services import gerar_agenda_contrato
from django.db import transaction
from financeiro_fit.services import gerar_parcelas_contrato

class HorarioFixoInline(admin.TabularInline):
    model = HorarioFixo
    formset = HorarioFixoFormSet # <--- Aplica a validação de quantidade
    extra = 1

@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'plano', 'data_inicio', 'data_fim', 'status']
    inlines = [HorarioFixoInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        def processar_tudo():
            gerar_agenda_contrato(form.instance)
            gerar_parcelas_contrato(form.instance) # <--- ADICIONE ISSO
        
        # O PULO DO GATO:
        # Isso diz: "Django, espera salvar TUDO no banco. Quando terminar, roda a agenda."
        transaction.on_commit(processar_tudo)

@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'valor_mensal', 'frequencia_semanal', 'organizacao']

@admin.register(TemplateContrato)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ['nome', 'organizacao', 'ativo']