from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import TemplateMensagem, ConexaoWhatsapp, LogEnvio
from .utils import enviar_mensagem_evolution
from cadastros_fit.models import Aluno
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ConexaoWhatsapp, TemplateMensagem
from .forms import ConexaoWhatsappForm, TemplateMensagemForm

def processar_e_enviar(aluno, template, dados_extras=None):
    """
    Pega o template, substitui as variáveis e envia.
    """
    texto = template.conteudo
    
    # Substituições base
    texto = texto.replace('[[aluno]]', aluno.nome)
    texto = texto.replace('[[telefone]]', aluno.telefone)
    
    # Se tiver dados de aula (data/horário)
    if dados_extras:
        if 'horario' in dados_extras:
            texto = texto.replace('[[horario]]', dados_extras['horario'])
        if 'data' in dados_extras:
            texto = texto.replace('[[data]]', dados_extras['data'])

    # Envia via Evolution
    sucesso, resposta = enviar_mensagem_evolution(aluno.organizacao, aluno.telefone, texto)
    
    # Grava Log
    LogEnvio.objects.create(
        organizacao=aluno.organizacao,
        aluno=aluno,
        mensagem=texto,
        status='ENVIADO' if sucesso else f'ERRO: {resposta}'
    )
    return sucesso

# VIEW PARA O BOTÃO DE COBRANÇA NO PERFIL
def disparar_cobranca_manual(request, aluno_id):
    aluno = get_object_or_404(Aluno, id=aluno_id)
    # Busca o template de cobrança ativo desta organização
    template = TemplateMensagem.objects.filter(
        organizacao=request.tenant, 
        gatilho='COBRANCA', 
        ativo=True
    ).first()
    
    if not template:
        return JsonResponse({'status': 'error', 'message': 'Template de cobrança não configurado.'})

    if processar_e_enviar(aluno, template):
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'message': 'Erro ao enviar WhatsApp.'})

def whatsapp_dashboard(request):
    """
    Tela principal de configurações do WhatsApp
    """
    # Busca a conexão da organização atual (Tenant)
    conexao, created = ConexaoWhatsapp.objects.get_or_create(organizacao=request.tenant)
    
    # Busca todos os templates de mensagem desta organização
    templates = TemplateMensagem.objects.filter(organizacao=request.tenant)
    
    if request.method == 'POST':
        form_conexao = ConexaoWhatsappForm(request.POST, instance=conexao)
        if form_conexao.is_valid():
            form_conexao.save()
            messages.success(request, "Configurações de API atualizadas!")
            return redirect('whatsapp_dashboard')
    else:
        form_conexao = ConexaoWhatsappForm(instance=conexao)

    return render(request, 'comunicacao_fit/dashboard.html', {
        'form_conexao': form_conexao,
        'templates': templates,
        'conexao': conexao
    })

def template_edit(request, pk=None):
    """
    View para Criar ou Editar um Template (Niver, Aula, Cobrança)
    """
    if pk:
        template = get_object_or_404(TemplateMensagem, pk=pk, organizacao=request.tenant)
    else:
        template = TemplateMensagem(organizacao=request.tenant)

    if request.method == 'POST':
        form = TemplateMensagemForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo de mensagem salvo com sucesso!")
            return redirect('whatsapp_dashboard')
    else:
        form = TemplateMensagemForm(instance=template)

    return render(request, 'comunicacao_fit/template_form.html', {'form': form, 'template': template})