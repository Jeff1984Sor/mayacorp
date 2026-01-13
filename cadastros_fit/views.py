from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone 
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from cadastros_fit.models import Aluno
from comunicacao_fit.models import ConexaoWhatsapp, LogEnvio
# Imports Locais
from .models import Aluno, Profissional, Unidade
from .forms import AlunoForm, ProfissionalForm, UnidadeForm, DocumentoExtraForm
from .services import OCRService
from comunicacao_fit.models import LogEnvio, TemplateMensagem
# Imports de Outros Apps
from agenda_fit.models import Presenca, Aula 
from financeiro_fit.models import Lancamento
from contratos_fit.models import Contrato
from .models import TipoServico
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import get_user_model

from cadastros_fit.models import Profissional

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
    # O form_valid manual não é mais necessário (Model sem organização)

class AlunoUpdateView(LoginRequiredMixin, UpdateView):
    model = Aluno
    form_class = AlunoForm
    template_name = 'cadastros_fit/aluno_form.html'
    success_url = reverse_lazy('aluno_list')

class AlunoDeleteView(LoginRequiredMixin, DeleteView):
    model = Aluno
    template_name = 'cadastros_fit/aluno_confirm_delete.html'
    success_url = reverse_lazy('aluno_list')

class AlunoDetailView(LoginRequiredMixin, DetailView):
    model = Aluno
    template_name = 'cadastros_fit/aluno_detail.html'
    context_object_name = 'aluno'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        aluno = self.object
        agora = timezone.now()
        context['agora'] = agora

        # --- ABA 1: VISÃO GERAL (Resumos) ---
        context['proxima_aula'] = Aula.objects.filter(
            presencas__aluno=aluno,
            data_hora_inicio__gte=agora,
            status='AGENDADA'
        ).order_by('data_hora_inicio').first()

        context['ultima_evolucao'] = Aula.objects.filter(
            presencas__aluno=aluno,
            data_hora_inicio__lt=agora,
        ).exclude(evolucao_texto='').order_by('-data_hora_inicio').first()

        # --- ABA 2: AGENDA COMPLETA ---
        context['agenda_completa'] = Presenca.objects.filter(
            aluno=aluno
        ).select_related('aula', 'aula__profissional').order_by('-aula__data_hora_inicio')

        # --- ABA 3: FINANCEIRO COMPLETO ---
        context['financeiro_completo'] = Lancamento.objects.filter(
            aluno=aluno
        ).select_related('categoria').order_by('data_vencimento')

        # --- ABA 4: CONTRATOS ---
        context['contratos_completo'] = Contrato.objects.filter(
            aluno=aluno
        ).select_related('plano').order_by('-criado_em')

        # --- NOVA ABA: HISTÓRICO WHATSAPP ---
        # Tenta buscar os logs. Se o banco der erro (tabela não existe), retorna lista vazia.
        try:
            context['historico_whatsapp'] = LogEnvio.objects.filter(
                aluno=aluno
            ).order_by('-data_hora')
        except:
            context['historico_whatsapp'] = []

        # Docs Extras
        context['documentos_extras'] = aluno.documentos.all()
        
        return context


# --- PROFISSIONAIS ---
class ProfissionalListView(LoginRequiredMixin, ListView):
    model = Profissional
    template_name = 'cadastros_fit/profissional_list.html'
    context_object_name = 'profissionais'

User = get_user_model()

@login_required
@transaction.atomic
def profissional_form(request, pk=None):
    profissional = get_object_or_404(Profissional, pk=pk) if pk else None
    user = profissional.user if profissional else None

    if request.method == "POST":
        # ===================== USER =====================
        username = request.POST.get("username")
        password = request.POST.get("password")
        perfil = request.POST.get("perfil")

        if not user:
            # CRIA USER
            if User.objects.filter(username=username).exists():
                messages.error(request, "Usuário já existe.")
                return redirect(request.path)

            user = User.objects.create_user(
                username=username,
                password=password,
                organizacao=request.user.organizacao,
                is_staff=(perfil == "ADMIN"),
            )
        else:
            # ATUALIZA USER
            if password:
                user.set_password(password)

            user.is_staff = (perfil == "ADMIN")
            user.save()

        # ================= PROFISSIONAL =================
        if not profissional:
            profissional = Profissional(user=user)

        profissional.nome = request.POST.get("nome")
        profissional.cpf = request.POST.get("cpf")
        profissional.email = request.POST.get("email")
        profissional.telefone = request.POST.get("telefone")
        profissional.crefito = request.POST.get("crefito")
        profissional.valor_hora_aula = request.POST.get("valor_hora_aula") or 0
        profissional.cor_agenda = request.POST.get("cor_agenda") or "#802422"
        profissional.perfil = perfil
        profissional.ativo = request.POST.get("ativo") == "on"

        profissional.save()

        messages.success(request, "Profissional salvo com sucesso.")
        return redirect("profissional_list")

    return render(request, "cadastros_fit/profissional_form.html", {
        "object": profissional
    })

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

# --- APIS E UTILITÁRIOS ---

@csrf_exempt 
def api_ler_documento(request):
    if request.method == 'POST' and request.FILES.get('imagem'):
        tipo = request.POST.get('tipo') 
        imagem = request.FILES['imagem']
        
        if tipo == 'identidade':
            dados = OCRService.extrair_dados_identidade(imagem)
        elif tipo == 'endereco':
            dados = OCRService.extrair_dados_endereco(imagem)
        else:
            return JsonResponse({'erro': 'Tipo inválido'}, status=400)
            
        return JsonResponse(dados)
    
    return JsonResponse({'erro': 'Envie uma imagem via POST'}, status=400)

def upload_documento_extra(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    
    if request.method == 'POST':
        # IMPORTANTE: passar request.FILES aqui!
        form = DocumentoExtraForm(request.POST, request.FILES)
        
        if form.is_valid():
            doc = form.save(commit=False)
            doc.aluno = aluno
            doc.save()
            messages.success(request, "Documento anexado com sucesso!")
        else:
            # Isso vai te mostrar no log ou na tela qual o erro (ex: arquivo muito grande, formato inválido)
            messages.error(request, f"Erro no upload: {form.errors}")
            
    return redirect('aluno_detail', pk=pk)

@csrf_exempt
def api_agenda_amanha(request):
    # Token simples para proteger (defina o mesmo no N8N)
    API_KEY = "segredo_mayacorp_123"
    
    token = request.headers.get('X-API-KEY')
    if token != API_KEY:
        return JsonResponse({'erro': 'Acesso negado'}, status=403)

    amanha = timezone.now().date() + timedelta(days=1)
    
    # Busca aulas de amanhã
    aulas = Aula.objects.filter(
        data_hora_inicio__date=amanha
    ).exclude(status='CANCELADA').select_related('profissional').prefetch_related('presencas__aluno')

    dados_envio = []

    for aula in aulas:
        # Monta o objeto
        dados_envio.append({
            "profissional": aula.profissional.nome,
            # "email_prof": aula.profissional.email, # Cuidado: Seu model Profissional tem email? Se não, comente.
            "horario": aula.data_hora_inicio.strftime('%H:%M'),
            "alunos": [p.aluno.nome for p in aula.presencas.all()]
        })

    return JsonResponse(dados_envio, safe=False)


def cobrar_aluno_whatsapp(request, aluno_id):
    """
    Busca o template de cobrança e dispara para o aluno
    """
    from comunicacao_fit.utils import enviar_mensagem_evolution # Importe aqui para evitar loop
    
    aluno = get_object_or_404(Aluno, id=aluno_id)
    
    # Busca o template de cobrança manual ativo
    template = TemplateMensagem.objects.filter(
        organizacao=request.tenant, 
        gatilho='COBRANCA', 
        ativo=True
    ).first()
    
    if not template:
        return JsonResponse({'status': 'error', 'message': 'Template de cobrança não configurado.'})

    # Substitui as variáveis básicas
    texto = template.conteudo.replace('[[aluno]]', aluno.nome)
    # Se você tiver financeiro, pode adicionar aqui: texto = texto.replace('[[valor]]', ...)

    # Dispara o envio
    sucesso, resposta = enviar_mensagem_evolution(request.tenant, aluno.telefone, texto)
    
    # Salva o Log
    LogEnvio.objects.create(
        organizacao=request.tenant,
        aluno=aluno,
        mensagem=texto,
        status='ENVIADO' if sucesso else f'ERRO: {resposta}'
    )
    
    if sucesso:
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'message': resposta})

class TipoServicoListView(LoginRequiredMixin, ListView):
    model = TipoServico
    template_name = 'cadastros_fit/servico_list.html'
    context_object_name = 'servicos'

class TipoServicoCreateView(LoginRequiredMixin, CreateView):
    model = TipoServico
    fields = ['nome', 'cor', 'ativo']
    template_name = 'cadastros_fit/servico_form.html'
    success_url = reverse_lazy('servico_list')




