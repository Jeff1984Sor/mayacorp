from django.contrib import admin
from .models import ConfiguracaoWhatsapp, LogMensagem

@admin.register(ConfiguracaoWhatsapp)
class ConfigWhatsAdmin(admin.ModelAdmin):
    list_display = ['organizacao', 'nome_instancia', 'ativo']

@admin.register(LogMensagem)
class LogWhatsAdmin(admin.ModelAdmin):
    list_display = ['data_envio', 'aluno', 'telefone', 'status', 'tipo']
    list_filter = ['status', 'tipo', 'data_envio']
    readonly_fields = ['data_envio', 'resposta_api']