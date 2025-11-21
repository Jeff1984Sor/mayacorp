from django.contrib import admin
from .models import CategoriaFinanceira, ContaBancaria, Lancamento

@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display = ['descricao', 'valor', 'data_vencimento', 'status', 'categoria']
    list_filter = ['status', 'categoria', 'data_vencimento']
    search_fields = ['descricao', 'aluno__nome']

@admin.register(ContaBancaria)
class ContaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'saldo_atual', 'organizacao']
    readonly_fields = ['saldo_atual'] # O saldo é calculado sozinho, ninguém mexe na mão!

@admin.register(CategoriaFinanceira)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo', 'organizacao']