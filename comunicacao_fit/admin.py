from django.contrib import admin
from .models import ConexaoWhatsapp, TemplateMensagem, LogEnvio

@admin.register(ConexaoWhatsapp)
class ConexaoWhatsappAdmin(admin.ModelAdmin):
    list_display = ('organizacao', 'instancia', 'ativo')

@admin.register(TemplateMensagem)
class TemplateMensagemAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'gatilho', 'horario_envio', 'ativo')
    list_filter = ('gatilho', 'ativo')

@admin.register(LogEnvio)
class LogEnvioAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'status', 'data_hora')
    readonly_fields = ('data_hora',)