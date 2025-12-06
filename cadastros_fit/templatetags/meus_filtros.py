from django import template
import re

register = template.Library()

@register.filter(name='apenas_numeros')
def apenas_numeros(valor):
    """Remove tudo que não for dígito"""
    if valor:
        return re.sub(r'\D', '', str(valor))
    return ''