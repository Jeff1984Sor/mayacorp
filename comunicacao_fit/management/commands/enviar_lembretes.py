from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from agenda_fit.models import Aula, Presenca
from comunicacao_fit.services import enviar_whatsapp
from comunicacao_fit.models import ConfiguracaoWhatsapp

class Command(BaseCommand):
    help = 'Envia lembretes de WhatsApp para aulas de amanhã'

    def handle(self, *args, **kwargs):
        amanha = timezone.now().date() + timedelta(days=1)
        
        # Pega aulas de amanhã que estão AGENDADAS
        aulas = Aula.objects.filter(
            data_hora_inicio__date=amanha,
            status='AGENDADA'
        )
        
        self.stdout.write(f"Encontradas {aulas.count()} aulas para {amanha}")
        
        for aula in aulas:
            # Pega a config da organização dessa aula
            config = ConfiguracaoWhatsapp.objects.filter(organizacao=aula.organizacao, ativo=True).first()
            if not config:
                continue

            # Para cada aluno na aula
            for presenca in aula.presencas.all():
                aluno = presenca.aluno
                
                # Monta o texto substituindo variáveis
                msg = config.mensagem_confirmacao
                msg = msg.replace("{{aluno}}", aluno.nome.split()[0]) # Primeiro nome
                msg = msg.replace("{{horario}}", aula.data_hora_inicio.strftime('%H:%M'))
                msg = msg.replace("{{unidade}}", aula.unidade.nome)
                
                # Envia
                sucesso, retorno = enviar_whatsapp(aluno, msg, tipo="LEMBRETE_AULA")
                
                if sucesso:
                    self.stdout.write(self.style.SUCCESS(f"Enviado para {aluno.nome}"))
                    # Opcional: Mudar status da aula para 'CONFIRMADA' se quiser assumir confirmação
                else:
                    self.stdout.write(self.style.ERROR(f"Erro {aluno.nome}: {retorno}"))