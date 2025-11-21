from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from contratos_fit.models import Contrato
from agenda_fit.models import Aula, Presenca
from cadastros_fit.models import Unidade

class Command(BaseCommand):
    help = 'Gera a agenda dos próximos 30 dias com base nos contratos ativos'

    def handle(self, *args, **kwargs):
        hoje = timezone.now().date()
        data_limite = hoje + timedelta(days=30)
        
        # Pega contratos ativos
        contratos = Contrato.objects.filter(status='ATIVO', data_fim__gte=hoje)
        
        aulas_criadas = 0
        
        for contrato in contratos:
            # Pega os horários fixos desse contrato (Ex: Seg 08:00)
            horarios = contrato.horarios_fixos.all()
            
            # Itera dia a dia pelos próximos 30 dias
            dia_atual = hoje
            while dia_atual <= data_limite:
                dia_semana_atual = dia_atual.weekday() # 0=Seg, 6=Dom
                
                # Verifica se tem horário fixo pra esse dia da semana
                for h in horarios:
                    if h.dia_semana == dia_semana_atual:
                        
                        # Monta a data/hora completa
                        inicio = timezone.make_aware(timezone.datetime.combine(dia_atual, h.horario))
                        fim = inicio + timedelta(hours=1) # Aula de 1h padrão
                        
                        # Verifica se já existe aula nesse horário com esse prof
                        # Se existir, usamos ela. Se não, criamos uma nova.
                        aula, created = Aula.objects.get_or_create(
                            data_hora_inicio=inicio,
                            profissional=h.profissional,
                            defaults={
                                'organizacao': contrato.plano.organizacao,
                                'unidade': Unidade.objects.first(), # Melhorar lógica depois pra pegar do contrato
                                'data_hora_fim': fim,
                                'status': 'AGENDADA'
                            }
                        )
                        
                        # Adiciona o aluno na lista de presença (se já não estiver)
                        if not aula.presencas.filter(aluno=contrato.aluno).exists():
                            # Verifica capacidade
                            if aula.presencas.count() < aula.capacidade_maxima:
                                Presenca.objects.create(aula=aula, aluno=contrato.aluno)
                                aulas_criadas += 1
                                self.stdout.write(f"Agendado: {contrato.aluno} em {inicio}")
                            else:
                                self.stdout.write(self.style.WARNING(f"Lotado: {inicio}"))
                
                dia_atual += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f'Processo finalizado! {aulas_criadas} agendamentos criados.'))