import requests
import json
from .models import LogMensagem, ConfiguracaoWhatsapp

def enviar_whatsapp(aluno, texto, tipo="MANUAL"):
    # 1. Pega a configuração da organização do aluno
    config = ConfiguracaoWhatsapp.objects.filter(organizacao=aluno.organizacao, ativo=True).first()
    
    if not config:
        return False, "Nenhuma configuração de WhatsApp ativa para esta organização."

    # 2. Limpa o telefone (apenas números)
    telefone = ''.join(filter(str.isdigit, aluno.telefone))
    if not telefone.startswith('55'):
        telefone = '55' + telefone # Adiciona DDI Brasil se faltar

    # 3. Monta a URL e Payload (Exemplo genérico para Z-API/Evolution)
    # Ajuste conforme a API que você contratar
    url = f"{config.url_api}/{config.nome_instancia}/token/{config.token_api}/send-text"
    
    payload = {
        "phone": telefone,
        "message": texto
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.token_api}" # Algumas APIs usam assim
    }

    # 4. Tenta enviar
    try:
        # response = requests.post(url, json=payload, headers=headers) # Descomente quando tiver a API real
        
        # --- SIMULAÇÃO (Para não quebrar sem API) ---
        class MockResponse:
            status_code = 200
            text = '{"message": "Enviado com sucesso (Simulado)"}'
        response = MockResponse()
        # --------------------------------------------

        status = 'ENVIADO' if response.status_code == 200 else 'ERRO'
        
        # 5. Grava o Log
        LogMensagem.objects.create(
            organizacao=aluno.organizacao,
            aluno=aluno,
            telefone=telefone,
            texto=texto,
            tipo=tipo,
            status=status,
            resposta_api=response.text
        )
        
        return True, "Mensagem enviada!"

    except Exception as e:
        LogMensagem.objects.create(
            organizacao=aluno.organizacao,
            aluno=aluno,
            telefone=telefone,
            texto=texto,
            tipo=tipo,
            status='ERRO',
            resposta_api=str(e)
        )
        return False, str(e)