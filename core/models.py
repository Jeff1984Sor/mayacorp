from django.contrib.auth.models import AbstractUser
from django.db import models

# 1. Criar a tabela de Produtos
class Produto(models.Model):
    nome = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, help_text="Identificador único no código (ex: gerador-pdf)")
    descricao = models.TextField(blank=True)

    def __str__(self):
        return self.nome

# 2. Atualizar o Usuário
class CustomUser(AbstractUser):
    telefone = models.CharField(max_length=15, blank=True, null=True, verbose_name="Telefone/WhatsApp")
    cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name="CPF")
    nome_empresa = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nome da Empresa")
    
    # Mantemos isso para controle geral
    is_assinante = models.BooleanField(default=False, verbose_name="É Assinante?")
    
    # NOVO: Lista de produtos que esse usuário comprou
    produtos = models.ManyToManyField(Produto, blank=True, verbose_name="Produtos Contratados")

    def __str__(self):
        return self.username
    