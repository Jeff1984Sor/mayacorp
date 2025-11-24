import os
import shutil
import json
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from core.decorators import possui_produto
from .services import processar_conciliacao_json_stream

# Função auxiliar para pegar a pasta do usuário
def get_user_temp_path(request):
    # Usa o username para criar uma pasta única na pasta media
    return os.path.join(settings.MEDIA_ROOT, 'temp_staging', str(request.user.username))

@possui_produto('gerador-pdf')
def gerador_home(request):
    base_path = get_user_temp_path(request)
    
    arquivos = {'boletos': [], 'comprovantes': []}
    
    # Verifica arquivos já existentes na pasta e lista eles
    for tipo in ['boletos', 'comprovantes']:
        path_tipo = os.path.join(base_path, tipo)
        if os.path.exists(path_tipo):
            # Filtra apenas PDFs para não mostrar lixo de sistema
            arquivos[tipo] = [f for f in os.listdir(path_tipo) if f.endswith('.pdf')]

    return render(request, 'pdf_tools/explorer.html', {'arquivos': arquivos})

@csrf_exempt
def api_upload_arquivo(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo') # 'boletos' ou 'comprovantes'
        arquivo = request.FILES.get('file')
        
        if tipo not in ['boletos', 'comprovantes'] or not arquivo:
            return JsonResponse({'error': 'Dados inválidos'}, status=400)

        # Garante que a pasta existe
        user_path = os.path.join(get_user_temp_path(request), tipo)
        os.makedirs(user_path, exist_ok=True)
        
        # Salva o arquivo (FileSystemStorage trata nomes duplicados automaticamente)
        fs = FileSystemStorage(location=user_path)
        filename = fs.save(arquivo.name, arquivo)
        
        return JsonResponse({'status': 'ok', 'filename': filename, 'tipo': tipo})
    
    return JsonResponse({'error': 'POST required'}, status=400)

@csrf_exempt
def api_delete_arquivo(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tipo = data.get('tipo')
            filename = data.get('filename')
            
            # Segurança: Garante que ninguém tente deletar arquivos fora da pasta temp
            safe_filename = os.path.basename(filename)
            path = os.path.join(get_user_temp_path(request), tipo, safe_filename)
            
            if os.path.exists(path):
                os.remove(path)
                return JsonResponse({'status': 'deleted'})
            else:
                return JsonResponse({'error': 'Arquivo não encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'POST required'}, status=400)

def api_iniciar_processamento(request):
    """
    Inicia o processamento e retorna um Stream (NDJSON)
    para alimentar o terminal na tela do usuário.
    """
    base_path = get_user_temp_path(request)
    path_boletos = os.path.join(base_path, 'boletos')
    path_comprovantes = os.path.join(base_path, 'comprovantes')
    
    # Validações Iniciais
    if not os.path.exists(path_boletos) or not os.listdir(path_boletos):
        return JsonResponse({'error': 'Nenhum boleto encontrado. Faça o upload primeiro.'}, status=400)
        
    arquivos_comp = os.listdir(path_comprovantes) if os.path.exists(path_comprovantes) else []
    if not arquivos_comp:
        return JsonResponse({'error': 'Nenhum comprovante encontrado.'}, status=400)
    
    # Pega o caminho completo do primeiro comprovante
    # (Filtra para garantir que é PDF e pega o primeiro)
    pdfs_comp = [f for f in arquivos_comp if f.endswith('.pdf')]
    if not pdfs_comp:
         return JsonResponse({'error': 'Arquivo de comprovante deve ser PDF.'}, status=400)

    caminho_comp_completo = os.path.join(path_comprovantes, pdfs_comp[0])
    
    # Lista completa dos boletos
    lista_boletos = [os.path.join(path_boletos, f) for f in os.listdir(path_boletos) if f.endswith('.pdf')]
    
    # Inicia o Stream JSON
    # Content-Type 'application/x-ndjson' avisa o navegador que é um stream de dados
    try:
        response = StreamingHttpResponse(
            processar_conciliacao_json_stream(lista_boletos, caminho_comp_completo, request.user),
            content_type='application/x-ndjson'
        )
        # Headers para evitar cache do navegador no stream
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no' # Importante para Nginx (se usar em produção)
        return response
    except Exception as e:
        return JsonResponse({'error': f'Erro ao iniciar stream: {str(e)}'}, status=500)

@csrf_exempt
def api_limpar_tudo(request):
    if request.method == 'POST':
        base_path = get_user_temp_path(request)
        
        if os.path.exists(base_path):
            try:
                # Remove a pasta inteira do usuário
                shutil.rmtree(base_path) 
                
                # Recria as pastas vazias imediatamente para evitar erro 
                # se o usuário tentar subir algo logo em seguida
                os.makedirs(os.path.join(base_path, 'boletos'), exist_ok=True)
                os.makedirs(os.path.join(base_path, 'comprovantes'), exist_ok=True)
                
                return JsonResponse({'status': 'ok'})
            except Exception as e:
                return JsonResponse({'error': f"Erro ao limpar disco: {str(e)}"}, status=500)
        
        # Se a pasta nem existia, tudo bem, considera limpo
        return JsonResponse({'status': 'ok'})
                
    return JsonResponse({'error': 'Método não permitido'}, status=405)