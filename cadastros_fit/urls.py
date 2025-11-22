from django.urls import path
from . import views

urlpatterns = [
    # Alunos
    path('alunos/', views.AlunoListView.as_view(), name='aluno_list'),
    path('alunos/novo/', views.AlunoCreateView.as_view(), name='aluno_create'),
    path('alunos/<int:pk>/editar/', views.AlunoUpdateView.as_view(), name='aluno_update'),
    path('alunos/<int:pk>/deletar/', views.AlunoDeleteView.as_view(), name='aluno_delete'),

    # Profissionais
    path('equipe/', views.ProfissionalListView.as_view(), name='profissional_list'),
    path('equipe/novo/', views.ProfissionalCreateView.as_view(), name='profissional_create'),
    path('equipe/<int:pk>/editar/', views.ProfissionalUpdateView.as_view(), name='profissional_update'),

    # Unidades
    path('unidades/', views.UnidadeListView.as_view(), name='unidade_list'),
    path('unidades/nova/', views.UnidadeCreateView.as_view(), name='unidade_create'),
    path('unidades/<int:pk>/editar/', views.UnidadeUpdateView.as_view(), name='unidade_update'),
    path('unidades/<int:pk>/deletar/', views.UnidadeDeleteView.as_view(), name='unidade_delete'),
]