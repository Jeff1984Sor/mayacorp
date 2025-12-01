from django.urls import path
from . import views

urlpatterns = [
    path('', views.LancamentoListView.as_view(), name='financeiro_lista'),
    path('baixar/<int:pk>/', views.baixar_lancamento, name='baixar_lancamento'),

    path('config/categorias/', views.CategoriaListView.as_view(), name='categoria_list'),
    path('config/categorias/nova/', views.CategoriaCreateView.as_view(), name='categoria_create'),
    
    path('config/contas/', views.ContaListView.as_view(), name='conta_list'),
    path('config/contas/nova/', views.ContaCreateView.as_view(), name='conta_create'),

    path('despesa/nova/', views.DespesaCreateView.as_view(), name='despesa_create'),
]