from django.db import models
import uuid

class TermoTemplate(models.Model):
    TIPO_CHOICES = [
        ('USO_IMAGEM', 'Uso de Imagem'),
        ('RESPONSABILIDADE', 'Termo de Responsabilidade'),
        ('LGPD', 'Consentimento LGPD'),
    ]
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='USO_IMAGEM')
    texto_html = models.TextField()
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

class TermoAssinado(models.Model):
    aluno = models.ForeignKey('cadastros_fit.Aluno', on_delete=models.CASCADE, related_name='termos')
    template = models.ForeignKey(TermoTemplate, on_delete=models.PROTECT)
    data_assinatura = models.DateTimeField(null=True, blank=True)
    assinatura_imagem = models.TextField(null=True, blank=True) # Base64
    ip_assinatura = models.GenericIPAddressField(null=True, blank=True)
    token_assinatura = models.UUIDField(default=uuid.uuid4, unique=True)

    def __str__(self):
        return f"{self.template.nome} - {self.aluno.nome}"