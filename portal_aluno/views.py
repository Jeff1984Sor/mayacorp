from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from agenda_fit.models import Aula, Presenca
from financeiro_fit.models import Lancamento
from cadastros_fit.models import Aluno

# Helper para pegar o aluno logado
def get_aluno(request):
    # Aqui assumimos que o email do User é igual ao do Aluno
    # Ou que existe um vínculo. Por enquanto, vamos pegar pelo email.
    return Aluno.objects.filter(email=request.user.email).first()

@login_required
def dashboard(request):
    aluno = get_aluno(request)
    if not aluno:
        return render(request, 'portal_aluno/erro_vinculo.html')

    # Próxima aula
    proxima_aula = Presenca.objects.filter(
        aluno=aluno, 
        aula__data_hora_inicio__gte=timezone.now(),
        status='PRESENTE'
    ).order_by('aula__data_hora_inicio').first()

    # Faturas em aberto
    faturas = Lancamento.objects.filter(
        aluno=aluno, 
        status='PENDENTE',
        categoria__tipo='RECEITA'
    ).count()

    return render(request, 'portal_aluno/dashboard.html', {
        'aluno': aluno,
        'proxima': proxima_aula,
        'faturas_pendentes': faturas
    })

@login_required
def minha_agenda(request):
    aluno = get_aluno(request)
    # Aulas futuras
    agendadas = Presenca.objects.filter(
        aluno=aluno,
        aula__data_hora_inicio__gte=timezone.now()
    ).order_by('aula__data_hora_inicio')
    
    return render(request, 'portal_aluno/agenda.html', {'agendadas': agendadas})

@login_required
def meu_financeiro(request):
    aluno = get_aluno(request)
    lancamentos = Lancamento.objects.filter(aluno=aluno).order_by('-data_vencimento')
    return render(request, 'portal_aluno/financeiro.html', {'lancamentos': lancamentos})

@login_required
def cancelar_aula(request, aula_id):
    aluno = get_aluno(request)
    presenca = get_object_or_404(Presenca, aula=aula_id, aluno=aluno)
    
    # Regra: Só pode cancelar com X horas de antecedência?
    # Por enquanto libera geral
    presenca.delete() # Ou muda status para CANCELADO
    
    messages.success(request, "Aula cancelada com sucesso.")
    return redirect('aluno_agenda')

@login_required
def marcar_aula(request, aula_id):
    aluno = get_aluno(request)
    aula = get_object_or_404(Aula, id=aula_id)
    
    # 1. Verifica se já está inscrito
    if Presenca.objects.filter(aula=aula, aluno=aluno).exists():
        messages.warning(request, "Você já está agendado nesta aula.")
        return redirect('aluno_agenda')

    # 2. Verifica se tem vaga (Capacidade)
    if aula.presencas.count() >= aula.capacidade_maxima:
        messages.error(request, "Esta aula já está lotada.")
        return redirect('aluno_agenda')

    # 3. Realiza o agendamento
    Presenca.objects.create(aula=aula, aluno=aluno, status='PRESENTE')
    
    messages.success(request, "Aula agendada com sucesso!")
    return redirect('aluno_agenda')