from django.contrib import admin
from .models import Unidade, Profissional, Aluno, DocumentoAluno, DispositivoAcesso, LogAcesso

@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'telefone', 'endereco')
    search_fields = ('nome',)

@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'crefito', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'cpf')

class DocumentoInline(admin.TabularInline):
    model = DocumentoAluno
    extra = 0

@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'telefone', 'ativo', 'bloqueado_catraca')
    list_filter = ('ativo', 'bloqueado_catraca')
    search_fields = ('nome', 'cpf', 'email')
    inlines = [DocumentoInline]

@admin.register(DispositivoAcesso)
class DispositivoAcessoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'unidade', 'ip_address')
    list_filter = ('unidade',)

@admin.register(LogAcesso)
class LogAcessoAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'dispositivo', 'direcao', 'status', 'data_hora')
    list_filter = ('status', 'direcao', 'data_hora')
    readonly_fields = ('data_hora',)