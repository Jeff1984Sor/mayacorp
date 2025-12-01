from django.urls import path
from . import views

urlpatterns = [
    path('novo/<int:aluno_id>/', views.novo_contrato, name='novo_contrato'),
    path('imprimir/<int:pk>/', views.imprimir_contrato, name='imprimir_contrato'),
]