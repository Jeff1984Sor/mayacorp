import requests
import json
from .models import ConfiguracaoIntegracao

class TotalPassService:
    # Endpoint de validação (Check-in)
    API_URL = "https://api.totalpass.com/service/v1/track_usages"

    @classmethod
    def get_token(cls):
        """
        Busca o token ativo no banco de dados do cliente atual.
        """
        try:
            config = ConfiguracaoIntegracao.objects.first()
            if config and config.totalpass_ativo:
                return config.totalpass_token
        except Exception as e:
            print(f"Erro ao buscar configuração TotalPass: {e}")
        return None

    @classmethod
    def validar_token(cls, token_diario_aluno):
        """
        Envia o token para a TotalPass validar e registrar o uso.
        """
        # 1. Busca o token da API no banco
        api_token = cls.get_token()
        
        if not api_token:
            return {
                "sucesso": False, 
                "mensagem": "Integração TotalPass não está configurada ou ativa neste sistema."
            }

        # 2. Prepara a requisição
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}", # A maioria usa Bearer, confirme se não é x-api-key
        }

        payload = {
            "token": token_diario_aluno
            # "gym_id": "12345" # Se precisar enviar ID da unidade, adicione ao model de Configuração e pegue aqui
        }

        try:
            # 3. Envia para a TotalPass
            response = requests.post(cls.API_URL, json=payload, headers=headers, timeout=10)
            
            print(f"TotalPass Response: {response.status_code} - {response.text}")

            # 4. Trata a resposta
            if response.status_code in [200, 201]:
                return {
                    "sucesso": True,
                    "mensagem": "Check-in TotalPass APROVADO! ✅",
                    "dados": response.json() if response.content else {}
                }
            else:
                # Tenta ler a mensagem de erro amigável
                try:
                    erro_msg = response.json().get('message') or response.json().get('error')
                except:
                    erro_msg = response.text
                
                return {
                    "sucesso": False,
                    "mensagem": f"Erro TotalPass: {erro_msg}"
                }

        except Exception as e:
            return {"sucesso": False, "mensagem": f"Erro de conexão: {str(e)}"}