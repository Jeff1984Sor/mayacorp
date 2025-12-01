from django.shortcuts import render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Aluno, Profissional, Unidade
from .forms import AlunoForm, ProfissionalForm, UnidadeForm
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import OCRService
from django.views.generic import DetailView
from django.shortcuts import get_object_or_404, redirect
from .forms import DocumentoExtraForm
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone # Importante para saber data atual
from .models import Aluno
from agenda_fit.models import Presenca, Aula 
# --- ALUNOS ---
class AlunoListView(LoginRequiredMixin, ListView):
    model = Aluno
    template_name = 'cadastros_fit/aluno_list.html'
    context_object_name = 'alunos'

class AlunoCreateView(LoginRequiredMixin, CreateView):
    model = Aluno
    form_class = AlunoForm
    template_name = 'cadastros_fit/aluno_form.html'
    success_url = reverse_lazy('aluno_list')

class AlunoUpdateView(LoginRequiredMixin, UpdateView):
    model = Aluno
    form_class = AlunoForm
    template_name = 'cadastros_fit/aluno_form.html'
    success_url = reverse_lazy('aluno_list')

class AlunoDeleteView(LoginRequiredMixin, DeleteView):
    model = Aluno
    template_name = 'cadastros_fit/aluno_confirm_delete.html'
    success_url = reverse_lazy('aluno_list')

# --- PROFISSIONAIS ---
class ProfissionalListView(LoginRequiredMixin, ListView):
    model = Profissional
    template_name = 'cadastros_fit/profissional_list.html'
    context_object_name = 'profissionais'

class ProfissionalCreateView(LoginRequiredMixin, CreateView):
    model = Profissional
    form_class = ProfissionalForm
    template_name = 'cadastros_fit/profissional_form.html'
    success_url = reverse_lazy('profissional_list')

class ProfissionalUpdateView(LoginRequiredMixin, UpdateView):
    model = Profissional
    form_class = ProfissionalForm
    template_name = 'cadastros_fit/profissional_form.html'
    success_url = reverse_lazy('profissional_list')

# --- UNIDADES ---
class UnidadeListView(LoginRequiredMixin, ListView):
    model = Unidade
    template_name = 'cadastros_fit/unidade_list.html'
    context_object_name = 'unidades'

class UnidadeCreateView(LoginRequiredMixin, CreateView):
    model = Unidade
    form_class = UnidadeForm
    template_name = 'cadastros_fit/unidade_form.html'
    success_url = reverse_lazy('unidade_list')

class UnidadeUpdateView(LoginRequiredMixin, UpdateView):
    model = Unidade
    form_class = UnidadeForm
    template_name = 'cadastros_fit/unidade_form.html'
    success_url = reverse_lazy('unidade_list')

class UnidadeDeleteView(LoginRequiredMixin, DeleteView):
    model = Unidade
    template_name = 'cadastros_fit/unidade_confirm_delete.html'
    success_url = reverse_lazy('unidade_list')

@csrf_exempt # Facilitar o POST via JS por enquanto
def api_ler_documento(request):
    if request.method == 'POST' and request.FILES.get('imagem'):
        tipo = request.POST.get('tipo') # 'identidade' ou 'endereco'
        imagem = request.FILES['imagem']
        
        print(f"🤖 Iniciando leitura de {tipo} via IA...")
        
        if tipo == 'identidade':
            dados = OCRService.extrair_dados_identidade(imagem)
        elif tipo == 'endereco':
            dados = OCRService.extrair_dados_endereco(imagem)
        else:
            return JsonResponse({'erro': 'Tipo inválido'}, status=400)
            
        return JsonResponse(dados)
    
    return JsonResponse({'erro': 'Envie uma imagem via POST'}, status=400)

class AlunoDetailView(LoginRequiredMixin, DetailView):
    model = Aluno
    template_name = 'cadastros_fit/aluno_detail.html'
    context_object_name = 'aluno'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        aluno = self.object
        agora = timezone.now()

        # 1. BUSCAR PRÓXIMA AULA
        # Filtra presenças onde a aula é no futuro e está agendada/confirmada
        proxima_presenca = Presenca.objects.filter(
            aluno=aluno,
            aula__data_hora_inicio__gte=agora,
            aula__status__in=['AGENDADA', 'CONFIRMADA']
        ).select_related('aula', 'aula__profissional').order_by('aula__data_hora_inicio').first()
        
        context['proxima_aula'] = proxima_presenca.aula if proxima_presenca else None

        # 2. CONTAGEM DE PRESENÇAS (Para estatística)
        total_aulas = Presenca.objects.filter(aluno=aluno, aula__data_hora_inicio__lt=agora).count()
        total_faltas = Presenca.objects.filter(aluno=aluno, status='FALTA').count()
        context['total_aulas_realizadas'] = total_aulas
        context['total_faltas'] = total_faltas

        # 3. ÚLTIMA EVOLUÇÃO (Prontuário)
        # Pega a última aula realizada que tenha algum texto de evolução
        ultima_evolucao = Aula.objects.filter(
            presencas__aluno=aluno,
            data_hora_inicio__lt=agora,
        ).exclude(evolucao_texto='').order_by('-data_hora_inicio').first()

        context['ultima_evolucao'] = ultima_evolucao

        # Documentos extras (que já tinha)
        context['documentos_extras'] = aluno.documentos.all()
        
        return context
    
def upload_documento_extra(request, pk):
    """Recebe o upload do Modal e salva vinculado ao Aluno (pk)"""
    aluno = get_object_or_404(Aluno, pk=pk)
    
    if request.method == 'POST':
        form = DocumentoExtraForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.aluno = aluno  # Vincula ao aluno da página
            doc.save()
            # Opcional: Mensagem de sucesso
    
    # Volta para a mesma ficha do aluno
    return redirect('aluno_detail', pk=pk)