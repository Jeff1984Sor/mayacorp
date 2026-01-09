from django.db import models
from core.models import Organizacao
from cadastros_fit.models import Aluno

class ConexaoWhatsapp(models.Model):
    """Configuração técnica da Evolution API"""
    organizacao = models.OneToOneField(Organizacao, on_delete=models.CASCADE)
    instancia = models.CharField(max_length=100, help_text="Nome da instância na Evolution")
    apikey = models.CharField(max_length=255, help_text="ApiKey da instância")
    url_base = models.URLField(default="https://api.sua-evolution.com")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"Conexão {self.organizacao.nome}"

class TemplateMensagem(models.Model):
    """Modelos de mensagens que você vai criar (Ex: Niver, Cobrança)"""
    TIPO_GATILHO = [
        ('AULA_AMANHA', 'Confirmação de Aula (Dia Anterior)'),
        ('ANIVERSARIO', 'Aniversário do Aluno'),
        ('COBRANCA', 'Cobrança Manual (Botão)'),
        ('BOAS_VINDAS', 'Boas-vindas (Novo Aluno)'),
    ]

    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE)
    titulo = models.CharField(max_length=100, help_text="Ex: Mensagem de Confirmação")
    gatilho = models.CharField(max_length=30, choices=TIPO_GATILHO)
    
    # É aqui que você escreve a mensagem no sistema
    conteudo = models.TextField(
        help_text="Variáveis: [[aluno]], [[data]], [[horario]], [[valor]]"
    )
    
    # Agendamento de horário
    horario_envio = models.TimeField(null=True, blank=True, help_text="Para mensagens automáticas")
    
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.titulo} ({self.get_gatilho_display()})"

class LogEnvio(models.Model):
    """Histórico de tudo que foi enviado"""
    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE)
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    mensagem = models.TextField()
    status = models.CharField(max_length=20) # Enviado, Erro
    data_hora = models.DateTimeField(auto_now_add=True)