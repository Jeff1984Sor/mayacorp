from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.contrib import messages
from django.db.models import Sum

# Imports dos Models e Forms
from .models import Lancamento, CategoriaFinanceira, ContaBancaria
from .forms import CategoriaForm, ContaBancariaForm, DespesaForm
from cadastros_fit.models import Aluno

# ==============================================================================
# 1. LANÇAMENTOS (EXTRATO)
# ==============================================================================

class LancamentoListView(LoginRequiredMixin, ListView):
    model = Lancamento
    template_name = 'financeiro_fit/lancamento_list.html'
    context_object_name = 'lancamentos'
    paginate_by = 50 

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros da URL
        status = self.request.GET.get('status')
        inicio = self.request.GET.get('inicio')
        fim = self.request.GET.get('fim')
        aluno_id = self.request.GET.get('aluno_id')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if inicio and fim:
            queryset = queryset.filter(data_vencimento__range=[inicio, fim])
            
        if aluno_id:
            queryset = queryset.filter(aluno__id=aluno_id)
            
        # Ordena: Pendentes primeiro, depois por data
        return queryset.order_by('status', 'data_vencimento')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['hoje'] = timezone.now().date()
        
        # Título personalizado se filtrar por aluno
        aluno_id = self.request.GET.get('aluno_id')
        if aluno_id:
            context['aluno_filtro'] = Aluno.objects.filter(pk=aluno_id).first()
            
        # Totais do Rodapé
        qs = self.get_queryset()
        context['total_receitas'] = qs.filter(categoria__tipo='RECEITA').aggregate(Sum('valor'))['valor__sum'] or 0
        context['total_despesas'] = qs.filter(categoria__tipo='DESPESA').aggregate(Sum('valor'))['valor__sum'] or 0
        
        return context

def baixar_lancamento(request, pk):
    """Marca um lançamento como PAGO e atualiza o saldo"""
    lancamento = get_object_or_404(Lancamento, pk=pk)
    
    if request.method == 'POST':
        # 1. Atualiza Lançamento
        lancamento.status = 'PAGO'
        lancamento.data_pagamento = timezone.now().date()
        lancamento.forma_pagamento = request.POST.get('forma_pagamento')
        lancamento.save()
        
        # 2. Atualiza Saldo
        conta = lancamento.conta
        if lancamento.categoria.tipo == 'RECEITA':
            conta.saldo_atual += lancamento.valor
        else:
            conta.saldo_atual -= lancamento.valor
        conta.save()
        
        messages.success(request, "Baixa realizada com sucesso!")
        
    return redirect('financeiro_lista')

# ==============================================================================
# 2. DESPESAS (Contas a Pagar)
# ==============================================================================

class DespesaCreateView(LoginRequiredMixin, CreateView):
    model = Lancamento
    form_class = DespesaForm
    template_name = 'financeiro_fit/despesa_form.html'
    success_url = reverse_lazy('financeiro_lista')

    def form_valid(self, form):
        # Garante que é uma despesa (caso o form não force)
        # form.instance.tipo_lancamento = 'DESPESA' (Se tiver esse campo no model)
        return super().form_valid(form)

# ==============================================================================
# 3. CADASTROS BÁSICOS (CATEGORIAS E CONTAS)
# ==============================================================================

# --- Categorias ---
class CategoriaListView(LoginRequiredMixin, ListView):
    model = CategoriaFinanceira
    template_name = 'financeiro_fit/categoria_list.html' # Ajustei para nome padrão
    context_object_name = 'categorias'

class CategoriaCreateView(LoginRequiredMixin, CreateView):
    model = CategoriaFinanceira
    form_class = CategoriaForm
    template_name = 'financeiro_fit/form_generico.html'
    success_url = reverse_lazy('categoria_list')

# --- Contas Bancárias ---
class ContaListView(LoginRequiredMixin, ListView):
    model = ContaBancaria
    template_name = 'financeiro_fit/conta_list.html' # Ajustei para nome padrão
    context_object_name = 'contas'

class ContaCreateView(LoginRequiredMixin, CreateView):
    model = ContaBancaria
    form_class = ContaBancariaForm
    template_name = 'financeiro_fit/form_generico.html'
    success_url = reverse_lazy('conta_list')