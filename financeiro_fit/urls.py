from django.urls import path
from . import views

urlpatterns = [
    path('', views.LancamentoListView.as_view(), name='financeiro_lista'),
    path('baixar/<int:pk>/', views.baixar_lancamento, name='baixar_lancamento'),
]