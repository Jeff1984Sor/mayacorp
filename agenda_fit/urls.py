from django.urls import path
from . import views

urlpatterns = [
    path('semanal/', views.calendario_semanal, name='calendario_semanal'),
    path('aula/<int:aula_id>/gerenciar/', views.gerenciar_aula, name='gerenciar_aula'),
]