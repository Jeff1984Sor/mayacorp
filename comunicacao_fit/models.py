from django.db import models
from core.models import Organizacao
from cadastros_fit.models import Aluno

class ConfiguracaoWhatsapp(models.Model):
    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE)
    nome_instancia = models.CharField(max_length=100, help_text="Nome da instância na API")
    token_api = models.CharField(max_length=255, help_text="Token de autenticação da API")
    url_api = models.URLField(default="https://api.z-api.io/instances/", help_text="Endpoint da API")
    
    mensagem_confirmacao = models.TextField(
        default="Olá {{aluno}}! Sua aula de Pilates está confirmada para amanhã às {{horario}}. Podemos contar com você?",
        help_text="Variáveis: {{aluno}}, {{horario}}, {{unidade}}"
    )
    
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"Config WhatsApp - {self.organizacao.nome}"

class LogMensagem(models.Model):
    STATUS_CHOICES = [('ENVIADO', 'Enviado'), ('ERRO', 'Erro'), ('AGUARDANDO', 'Aguardando')]
    
    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE)
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    telefone = models.CharField(max_length=20)
    texto = models.TextField()
    tipo = models.CharField(max_length=50, default="CONFIRMACAO_AULA")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AGUARDANDO')
    resposta_api = models.TextField(blank=True, null=True)
    data_envio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.aluno} - {self.status} ({self.data_envio})"