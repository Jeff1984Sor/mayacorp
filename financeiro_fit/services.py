from dateutil.relativedelta import relativedelta
from .models import Lancamento, CategoriaFinanceira, ContaBancaria

def gerar_parcelas_contrato(contrato):
    print(f"--- INICIANDO FINANCEIRO PARA CONTRATO {contrato.id} ---")
    
    # 1. Verifica se já existem parcelas (para não duplicar)
    if Lancamento.objects.filter(contrato=contrato).exists():
        print("AVISO: Já existem lançamentos para este contrato. Pulando geração.")
        return

    # 2. Busca Categoria
    categoria, created = CategoriaFinanceira.objects.get_or_create(
        organizacao=contrato.plano.organizacao,
        nome="Mensalidades",
        defaults={'tipo': 'RECEITA'}
    )
    if created:
        print("Categoria 'Mensalidades' criada automaticamente.")
    
    # 3. Busca Conta
    conta = ContaBancaria.objects.filter(organizacao=contrato.plano.organizacao).first()
    if not conta:
        print("ERRO CRÍTICO: Nenhuma conta bancária encontrada para a organização.")
        print("Por favor, cadastre uma conta em Financeiro > Contas Bancárias.")
        return

    print(f"Usando conta: {conta.nome}")

    # 4. Gera Parcelas
    data_base = contrato.data_inicio
    dia_vencimento = contrato.dia_vencimento
    qtd_parcelas = contrato.plano.duracao_meses
    
    print(f"Gerando {qtd_parcelas} parcelas. Dia vencimento: {dia_vencimento}")
    
    for i in range(qtd_parcelas):
        # Calcula data
        data_mes = data_base + relativedelta(months=i)
        
        # Ajusta dia
        try:
            vencimento = data_mes.replace(day=dia_vencimento)
        except ValueError:
            # Se cair dia 31 em mês de 30, pega o último dia
            vencimento = data_mes + relativedelta(day=31)

        print(f" >> Criando parcela {i+1}: {vencimento}")

        Lancamento.objects.create(
            organizacao=contrato.plano.organizacao,
            descricao=f"Mensalidade {i+1}/{qtd_parcelas} - {contrato.aluno.nome}",
            aluno=contrato.aluno,
            contrato=contrato,
            categoria=categoria,
            conta=conta,
            valor=contrato.plano.valor_mensal,
            data_vencimento=vencimento,
            status='PENDENTE'
        )
    
    print("--- FINANCEIRO CONCLUÍDO COM SUCESSO ---")