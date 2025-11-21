from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Aula, Presenca, MacroEvolucao

class PresencaInline(admin.TabularInline):
    model = Presenca
    extra = 1

@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ['data_hora_inicio', 'profissional', 'status', 'unidade']
    list_filter = ['status', 'profissional', 'data_hora_inicio']
    inlines = [PresencaInline] # Permite dar presença dentro da aula

@admin.register(MacroEvolucao)
class MacroAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'organizacao']