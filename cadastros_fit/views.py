from django.shortcuts import render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Aluno, Profissional, Unidade
from .forms import AlunoForm, ProfissionalForm, UnidadeForm

# --- MIXIN DE SEGURANÇA ---
class OrganizacaoFilterMixin:
    """Garante que o usuário só veja dados da sua própria empresa"""
    def get_queryset(self):
        qs = super().get_queryset()
        # Filtra pela organização vinculada ao usuário logado
        if self.request.user.organizacao:
            return qs.filter(organizacao=self.request.user.organizacao)
        return qs.none() # Se não tiver org, não vê nada

    def form_valid(self, form):
        # Vincula automaticamente a organização ao criar
        form.instance.organizacao = self.request.user.organizacao
        return super().form_valid(form)

# --- ALUNOS ---
class AlunoListView(LoginRequiredMixin, OrganizacaoFilterMixin, ListView):
    model = Aluno
    template_name = 'cadastros_fit/aluno_list.html'
    context_object_name = 'alunos'

class AlunoCreateView(LoginRequiredMixin, OrganizacaoFilterMixin, CreateView):
    model = Aluno
    form_class = AlunoForm
    template_name = 'cadastros_fit/aluno_form.html'
    success_url = reverse_lazy('aluno_list')

class AlunoUpdateView(LoginRequiredMixin, OrganizacaoFilterMixin, UpdateView):
    model = Aluno
    form_class = AlunoForm
    template_name = 'cadastros_fit/aluno_form.html'
    success_url = reverse_lazy('aluno_list')

class AlunoDeleteView(LoginRequiredMixin, OrganizacaoFilterMixin, DeleteView):
    model = Aluno
    template_name = 'cadastros_fit/aluno_confirm_delete.html'
    success_url = reverse_lazy('aluno_list')

# --- PROFISSIONAIS ---
class ProfissionalListView(LoginRequiredMixin, OrganizacaoFilterMixin, ListView):
    model = Profissional
    template_name = 'cadastros_fit/profissional_list.html'
    context_object_name = 'profissionais'

class ProfissionalCreateView(LoginRequiredMixin, OrganizacaoFilterMixin, CreateView):
    model = Profissional
    form_class = ProfissionalForm
    template_name = 'cadastros_fit/profissional_form.html'
    success_url = reverse_lazy('profissional_list')

class ProfissionalUpdateView(LoginRequiredMixin, OrganizacaoFilterMixin, UpdateView):
    model = Profissional
    form_class = ProfissionalForm
    template_name = 'cadastros_fit/profissional_form.html'
    success_url = reverse_lazy('profissional_list')

# --- UNIDADES ---
class UnidadeListView(LoginRequiredMixin, OrganizacaoFilterMixin, ListView):
    model = Unidade
    template_name = 'cadastros_fit/unidade_list.html'
    context_object_name = 'unidades'

class UnidadeCreateView(LoginRequiredMixin, OrganizacaoFilterMixin, CreateView):
    model = Unidade
    form_class = UnidadeForm
    template_name = 'cadastros_fit/unidade_form.html'
    success_url = reverse_lazy('unidade_list')

class UnidadeUpdateView(LoginRequiredMixin, OrganizacaoFilterMixin, UpdateView):
    model = Unidade
    form_class = UnidadeForm
    template_name = 'cadastros_fit/unidade_form.html'
    success_url = reverse_lazy('unidade_list')

class UnidadeDeleteView(LoginRequiredMixin, OrganizacaoFilterMixin, DeleteView):
    model = Unidade
    template_name = 'cadastros_fit/unidade_confirm_delete.html'
    success_url = reverse_lazy('unidade_list')