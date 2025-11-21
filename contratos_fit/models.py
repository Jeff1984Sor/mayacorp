from django.db import models
from core.models import Organizacao
from cadastros_fit.models import Aluno, Profissional, Unidade

class TemplateContrato(models.Model):
    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100, help_text="Ex: Contrato Padrão 2025")
    texto_html = models.TextField(help_text="Use {{aluno_nome}}, {{valor}}, {{data_inicio}} como variáveis.")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

class Plano(models.Model):
    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100, help_text="Ex: Pilates Solo 2x")
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2)
    frequencia_semanal = models.PositiveIntegerField(default=2, help_text="Quantas vezes por semana?")
    duracao_meses = models.PositiveIntegerField(default=12)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} - R$ {self.valor_mensal}"

class Contrato(models.Model):
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('PENDENTE', 'Pendente Assinatura'),
        ('CANCELADO', 'Cancelado'),
        ('ENCERRADO', 'Encerrado (Fim do Prazo)'),
    ]

    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name='contratos')
    plano = models.ForeignKey(Plano, on_delete=models.PROTECT) # Se apagar o plano, o contrato fica
    
    data_inicio = models.DateField()
    data_fim = models.DateField()
    dia_vencimento = models.PositiveIntegerField(default=10, help_text="Dia do mês para pagamento")
    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, verbose_name="Unidade de Atendimento")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    template_usado = models.ForeignKey(TemplateContrato, on_delete=models.SET_NULL, null=True, blank=True)
    arquivo_assinado = models.FileField(upload_to='contratos/assinados/', blank=True, null=True)
    
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Contrato {self.id} - {self.aluno.nome}"

# Essa tabela define a "Grade Fixa" do aluno (Ex: Toda Seg e Qua às 08:00)
class HorarioFixo(models.Model):
    DIAS_SEMANA = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='horarios_fixos')
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    horario = models.TimeField()
    profissional = models.ForeignKey(Profissional, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.get_dia_semana_display()} às {self.horario}"