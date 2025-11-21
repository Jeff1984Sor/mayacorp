from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Lancamento


@receiver(post_save, sender=Lancamento)
def atualizar_saldo(sender, instance, created, **kwargs):
    """
    Recalcula o saldo da conta bancária sempre que um lançamento é salvo.
    Lógica simplificada: Soma tudo que é PAGO dessa conta.
    """
    conta = instance.conta
    
    # Soma Receitas Pagas
    receitas = Lancamento.objects.filter(
        conta=conta, status='PAGO', categoria__tipo='RECEITA'
    ).aggregate(total=models.Sum('valor'))['total'] or 0
    
    # Soma Despesas Pagas
    despesas = Lancamento.objects.filter(
        conta=conta, status='PAGO', categoria__tipo='DESPESA'
    ).aggregate(total=models.Sum('valor'))['total'] or 0
    
    # Atualiza
    conta.saldo_atual = receitas - despesas
    conta.save()