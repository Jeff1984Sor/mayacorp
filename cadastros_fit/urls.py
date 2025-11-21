from django.urls import path
from . import views

urlpatterns = [
    path('alunos/', views.lista_alunos, name='lista_alunos'),
    path('alunos/novo/', views.novo_aluno, name='novo_aluno'),
    path('alunos/editar/<int:id>/', views.editar_aluno, name='editar_aluno'),
]