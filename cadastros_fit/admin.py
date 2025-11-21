from django.contrib import admin
from .models import Unidade, Profissional, Aluno, DocumentoAluno, DispositivoAcesso, LogAcesso
from django.shortcuts import render
from django.http import HttpResponseRedirect
from comunicacao_fit.services import enviar_whatsapp

class DocumentoInline(admin.TabularInline):
    model = DocumentoAluno
    extra = 0

# --- ALUNO (Tudo junto aqui) ---
@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'organizacao', 'telefone', 'ativo', 'bloqueado_catraca']
    search_fields = ['nome', 'cpf']
    list_filter = ['organizacao', 'ativo']
    inlines = [DocumentoInline]
    
    # Ação personalizada do WhatsApp
    actions = ['enviar_whatsapp_manual']

    def enviar_whatsapp_manual(self, request, queryset):
        for aluno in queryset:
            enviar_whatsapp(aluno, "Olá! Esta é uma mensagem manual do Studio.", tipo="MANUAL")
        
        self.message_user(request, f"Mensagens enviadas para {queryset.count()} alunos.")
    
    enviar_whatsapp_manual.short_description = "Enviar WhatsApp (Teste)"

# --- OUTROS MODELOS ---
@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ['nome', 'organizacao', 'valor_hora_aula', 'ativo']

@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ['nome', 'organizacao', 'telefone']

@admin.register(DispositivoAcesso)
class CatracaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'unidade', 'ip_address']

@admin.register(LogAcesso)
class LogAcessoAdmin(admin.ModelAdmin):
    list_display = ['data_hora', 'aluno', 'status', 'motivo_bloqueio']
    list_filter = ['status', 'direcao', 'data_hora']
    readonly_fields = ['data_hora', 'aluno', 'dispositivo', 'status', 'motivo_bloqueio']