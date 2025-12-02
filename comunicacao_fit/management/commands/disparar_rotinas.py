from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from cadastros_fit.models import Aluno
from agenda_fit.models import Presenca # Ajuste se o nome do app de agenda for outro
import requests

class Command(BaseCommand):
    help = 'Verifica notificações diárias: Aniversários, Lembretes de Aula e Contratos'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando rotina de notificações...")
        
        hoje = timezone.now().date()
        amanha = hoje + timedelta(days=1)
        
        # URL do seu n8n (pode ser a mesma do signals)
        N8N_URL = "https://SEU-LINK-DO-N8N.hooks.n8n.cloud/webhook/comunicacao"

        # ---------------------------------------------------------
        # 1. ANIVERSARIANTES DO DIA
        # ---------------------------------------------------------
        aniversariantes = Aluno.objects.filter(
            data_nascimento__day=hoje.day, 
            data_nascimento__month=hoje.month,
            ativo=True
        )
        
        count_niver = 0
        for aluno in aniversariantes:
            if aluno.telefone:
                payload = {
                    "tipo": "aniversario",
                    "nome": aluno.nome,
                    "telefone": aluno.telefone
                }
                requests.post(N8N_URL, json=payload)
                count_niver += 1
        
        self.stdout.write(f"- Aniversariantes enviados: {count_niver}")

        # ---------------------------------------------------------
        # 2. LEMBRETE DE AULA (PARA AMANHÃ)
        # ---------------------------------------------------------
        # Busca presenças agendadas para o dia seguinte
        presencas_amanha = Presenca.objects.filter(
            aula__data_hora_inicio__date=amanha,
            aula__status='AGENDADA' # Confirme se o status no seu model é esse mesmo
        ).select_related('aluno', 'aula', 'aula__profissional')

        count_aulas = 0
        for presenca in presencas_amanha:
            aluno = presenca.aluno
            if aluno.telefone:
                hora_aula = presenca.aula.data_hora_inicio.strftime('%H:%M')
                prof_nome = presenca.aula.profissional.nome if presenca.aula.profissional else "Instrutor"
                
                payload = {
                    "tipo": "lembrete_aula",
                    "nome": aluno.nome,
                    "telefone": aluno.telefone,
                    "dia": amanha.strftime('%d/%m'),
                    "horario": hora_aula,
                    "profissional": prof_nome
                }
                requests.post(N8N_URL, json=payload)
                count_aulas += 1

        self.stdout.write(f"- Lembretes de aula enviados: {count_aulas}")

        # ---------------------------------------------------------
        # 3. CONTRATO VENCENDO (Exemplo)
        # ---------------------------------------------------------
        # Como não vi o model de Contrato, deixo a lógica preparada:
        # contratos = Contrato.objects.filter(data_fim=hoje + timedelta(days=5), ativo=True)
        # ... loop e request post ...
        
        self.stdout.write(self.style.SUCCESS("Rotina finalizada com sucesso!"))