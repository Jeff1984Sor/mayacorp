import requests
import json

def enviar_mensagem_evolution(organizacao, telefone, mensagem):
    # Busca a configuração da API para esta organização
    from .models import ConexaoWhatsapp
    config = ConexaoWhatsapp.objects.filter(organizacao=organizacao, ativo=True).first()
    
    if not config:
        return False, "Configuração de API não encontrada ou inativa."

    # Limpa o telefone: mantém apenas números
    telefone_limpo = "".join(filter(str.isdigit, telefone))
    if not telefone_limpo.startswith("55"):
        telefone_limpo = "55" + telefone_limpo

    url = f"{config.url_base}/message/sendText/{config.instancia}"
    
    payload = {
        "number": telefone_limpo,
        "options": {"delay": 1200, "presence": "composing", "linkPreview": False},
        "textMessage": {"text": mensagem}
    }
    
    headers = {
        "Content-Type": "application/json",
        "apikey": config.apikey
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
        return response.status_code in [200, 201], response.text
    except Exception as e:
        return False, str(e)