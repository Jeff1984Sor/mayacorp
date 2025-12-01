from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.contrib import messages
from django.db.models import Sum
from cadastros_fit.models import Aluno 

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import CategoriaFinanceira, ContaBancaria
from .forms import CategoriaForm, ContaBancariaForm
from .forms import DespesaForm

from .models import Lancamento, ContaBancaria

class LancamentoListView(LoginRequiredMixin, ListView):
    model = Lancamento
    template_name = 'financeiro_fit/lancamento_list.html'
    context_object_name = 'lancamentos'
    paginate_by = 50 # Aumentei para ver mais parcelas de uma vez

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
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
            
        # Ordena: Atrasados primeiro, depois os futuros
        return queryset.order_by('status', 'data_vencimento')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Passa a data de hoje para calcular atrasos no HTML
        context['hoje'] = timezone.now().date()
        
        # Se estiver filtrando por aluno, passa o objeto aluno para o título
        aluno_id = self.request.GET.get('aluno_id')
        if aluno_id:
            context['aluno_filtro'] = Aluno.objects.filter(pk=aluno_id).first()
            
        # Totais (mantém a lógica anterior)
        qs = self.get_queryset()
        context['total_receitas'] = qs.filter(categoria__tipo='RECEITA').aggregate(Sum('valor'))['valor__sum'] or 0
        context['total_despesas'] = qs.filter(categoria__tipo='DESPESA').aggregate(Sum('valor'))['valor__sum'] or 0
        
        return context
    
# Função para Receber/Pagar (Dar Baixa)
def baixar_lancamento(request, pk):
    lancamento = get_object_or_404(Lancamento, pk=pk)
    
    if request.method == 'POST':
        # 1. Atualiza o Lançamento
        lancamento.status = 'PAGO'
        lancamento.data_pagamento = timezone.now().date()
        lancamento.forma_pagamento = request.POST.get('forma_pagamento')
        lancamento.save()
        
        # 2. Atualiza o Saldo da Conta Bancária
        conta = lancamento.conta
        if lancamento.categoria.tipo == 'RECEITA':
            conta.saldo_atual += lancamento.valor
        else:
            conta.saldo_atual -= lancamento.valor
        conta.save()
        
        messages.success(request, f"Lançamento '{lancamento.descricao}' baixado com sucesso!")
        
    return redirect('financeiro_lista')

# --- CATEGORIAS ---
class CategoriaListView(LoginRequiredMixin, ListView):
    model = CategoriaFinanceira
    template_name = 'financeiro_fit/config_categorias_list.html'
    context_object_name = 'categorias'

class CategoriaCreateView(LoginRequiredMixin, CreateView):
    model = CategoriaFinanceira
    form_class = CategoriaForm
    template_name = 'financeiro_fit/form_generico.html'
    success_url = reverse_lazy('categoria_list')

    # Se precisar injetar organizacao (se ainda existir no model):
    # def form_valid(self, form):
    #     form.instance.organizacao = self.request.tenant
    #     return super().form_valid(form)

# --- CONTAS BANCÁRIAS ---
class ContaListView(LoginRequiredMixin, ListView):
    model = ContaBancaria
    template_name = 'financeiro_fit/config_contas_list.html'
    context_object_name = 'contas'

class ContaCreateView(LoginRequiredMixin, CreateView):
    model = ContaBancaria
    form_class = ContaBancariaForm
    template_name = 'financeiro_fit/form_generico.html'
    success_url = reverse_lazy('conta_list')

class DespesaCreateView(LoginRequiredMixin, CreateView):
    model = Lancamento
    form_class = DespesaForm
    template_name = 'financeiro_fit/despesa_form.html'
    success_url = reverse_lazy('financeiro_lista')