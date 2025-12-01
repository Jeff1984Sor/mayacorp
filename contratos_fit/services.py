from datetime import timedelta
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from agenda_fit.models import Aula, Presenca
from financeiro_fit.models import Lancamento, CategoriaFinanceira, ContaBancaria

def processar_novo_contrato(contrato):
    """
    Gera Agenda e Financeiro sem depender do campo 'organizacao' (pois o Schema já isola).
    """
    
    print(f"🔄 Automação Contrato #{contrato.id}...")

    # --- 1. GERAR AGENDA ---
    horarios = contrato.horarios_fixos.all()
    if horarios.exists():
        data_atual = contrato.data_inicio
        data_fim = contrato.data_fim # Agora calculado no save() do model
        
        while data_atual <= data_fim:
            dia_semana_atual = data_atual.weekday()
            
            for h in horarios:
                if h.dia_semana == dia_semana_atual:
                    inicio = timezone.make_aware(timezone.datetime.combine(data_atual, h.horario))
                    fim = inicio + timedelta(hours=1)
                    
                    # Cria/Busca a aula (Sem passar organizacao)
                    aula, created = Aula.objects.get_or_create(
                        data_hora_inicio=inicio,
                        profissional=h.profissional,
                        defaults={
                            'unidade': contrato.unidade,
                            'data_hora_fim': fim,
                            'status': 'AGENDADA',
                            'capacidade_maxima': 3
                        }
                    )
                    
                    if aula.presencas.count() < aula.capacidade_maxima:
                        if not aula.presencas.filter(aluno=contrato.aluno).exists():
                            Presenca.objects.create(aula=aula, aluno=contrato.aluno)
            
            data_atual += timedelta(days=1)

    # --- 2. GERAR FINANCEIRO ---
    if contrato.valor_total > 0:
        valor_parcela = contrato.valor_total / contrato.qtde_parcelas
        
        # Pega categoria/conta padrão (primeira que achar, ou crie lógica específica)
        categoria = CategoriaFinanceira.objects.filter(tipo='RECEITA').first()
        conta = ContaBancaria.objects.first()
        
        if categoria and conta:
            for i in range(contrato.qtde_parcelas):
                data_venc = contrato.data_inicio + relativedelta(months=i)
                try:
                    data_venc = data_venc.replace(day=contrato.dia_vencimento)
                except ValueError:
                    data_venc = data_venc + relativedelta(day=31)

                # Cria lançamento (Sem passar organizacao)
                Lancamento.objects.create(
                    descricao=f"Mensalidade {i+1}/{contrato.qtde_parcelas} - {contrato.plano.nome}",
                    aluno=contrato.aluno,
                    contrato=contrato,
                    categoria=categoria,
                    conta=conta,
                    valor=valor_parcela,
                    data_vencimento=data_venc,
                    status='PENDENTE'
                )