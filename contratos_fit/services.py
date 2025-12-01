from datetime import timedelta
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db import transaction

# Imports dos Apps Integrados
from agenda_fit.models import Aula, Presenca
from financeiro_fit.models import Lancamento, CategoriaFinanceira, ContaBancaria

def processar_novo_contrato(contrato):
    """
    Função Mestre: 
    1. Gera a grade de aulas na Agenda (Agenda_fit).
    2. Gera as contas a receber no Financeiro (Financeiro_fit).
    """
    
    print(f"🔄 Processando automação para Contrato #{contrato.id} - {contrato.aluno.nome}...")

    # ==========================================================
    # PARTE 1: GERAR AGENDA (Aulas e Presenças)
    # ==========================================================
    horarios = contrato.horarios_fixos.all()
    
    if horarios.exists():
        data_atual = contrato.data_inicio
        data_fim = contrato.data_fim
        aulas_criadas = 0
        
        # Loop dia a dia, do início ao fim do contrato
        while data_atual <= data_fim:
            dia_semana_atual = data_atual.weekday() # 0=Seg, 6=Dom
            
            for h in horarios:
                if h.dia_semana == dia_semana_atual:
                    # Cria objeto datetime com fuso horário (Aware)
                    inicio = timezone.make_aware(timezone.datetime.combine(data_atual, h.horario))
                    fim = inicio + timedelta(hours=1) # Duração padrão de 1h (pode parametrizar depois)
                    
                    # 1. Busca aula existente ou cria nova (Turma)
                    aula, created = Aula.objects.get_or_create(
                        data_hora_inicio=inicio,
                        profissional=h.profissional, # Professor definido na grade do aluno
                        defaults={
                            'organizacao': contrato.plano.organizacao,
                            'unidade': contrato.unidade,
                            'data_hora_fim': fim,
                            'status': 'AGENDADA',
                            'capacidade_maxima': 3 # Capacidade padrão (ideal vir do Plano/Unidade)
                        }
                    )
                    
                    # 2. Verifica capacidade e Insere o Aluno
                    if aula.presencas.count() < aula.capacidade_maxima:
                        # Só insere se ele já não estiver lá
                        if not aula.presencas.filter(aluno=contrato.aluno).exists():
                            Presenca.objects.create(aula=aula, aluno=contrato.aluno)
                            aulas_criadas += 1
                    else:
                        print(f"❌ [ERRO] Aula lotada em {inicio}. Aluno não agendado.")
                        # Aqui você poderia criar um log de erro no banco para avisar a recepção
            
            data_atual += timedelta(days=1)
        
        print(f"✅ Agenda gerada com sucesso: {aulas_criadas} aulas agendadas.")
    else:
        print("⚠️ Nenhuma grade de horário definida. Agenda não gerada.")


    # ==========================================================
    # PARTE 2: GERAR FINANCEIRO (Parcelas a Receber)
    # ==========================================================
    if contrato.valor_total > 0 and contrato.qtde_parcelas > 0:
        
        valor_parcela = contrato.valor_total / contrato.qtde_parcelas
        
        # Busca Categoria e Conta padrão para lançar a receita
        # (Idealmente você deve ter uma configuração global para definir quem são esses padrões)
        categoria = CategoriaFinanceira.objects.filter(
            organizacao=contrato.plano.organizacao, 
            tipo='RECEITA'
        ).first()
        
        conta = ContaBancaria.objects.filter(organizacao=contrato.plano.organizacao).first()
        
        if categoria and conta:
            for i in range(contrato.qtde_parcelas):
                # Calcula Data de Vencimento
                # Data Início + X meses
                data_venc = contrato.data_inicio + relativedelta(months=i)
                
                # Ajusta para o dia de vencimento escolhido (Ex: dia 10)
                try:
                    data_venc = data_venc.replace(day=contrato.dia_vencimento)
                except ValueError:
                    # Se cair dia 31 num mês de 30 dias, pega o último dia do mês
                    data_venc = data_venc + relativedelta(day=31)

                # Cria o Lançamento
                Lancamento.objects.create(
                    organizacao=contrato.plano.organizacao,
                    descricao=f"Mensalidade {i+1}/{contrato.qtde_parcelas} - {contrato.plano.nome}",
                    aluno=contrato.aluno,
                    contrato=contrato,
                    categoria=categoria,
                    conta=conta,
                    valor=valor_parcela,
                    data_vencimento=data_venc,
                    status='PENDENTE'
                )
            print(f"✅ Financeiro gerado: {contrato.qtde_parcelas} parcelas criadas.")
        else:
            print("❌ Erro ao gerar financeiro: Não há Categoria ou Conta Bancária cadastrada.")