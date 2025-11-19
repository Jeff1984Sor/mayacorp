import os
import uuid
import shutil
from django.shortcuts import render
from django.http import HttpResponse, StreamingHttpResponse # <--- Importe Streaming
from django.conf import settings
from core.decorators import possui_produto
from .services import processar_conciliacao_stream # <--- Importe a nova função
from django.core.files.storage import FileSystemStorage

@possui_produto('gerador-pdf')
def gerador_home(request):
    if request.method == "POST":
        boletos = request.FILES.getlist('boletos')
        comprovantes = request.FILES.get('comprovantes')
        
        if boletos and comprovantes:
            operacao_id = str(uuid.uuid4())
            caminho_temp = os.path.join(settings.MEDIA_ROOT, 'temp', operacao_id)
            os.makedirs(caminho_temp, exist_ok=True)
            
            fs = FileSystemStorage(location=caminho_temp)
            
            try:
                lista_caminhos_boletos = []
                for bol in boletos:
                    filename = fs.save(bol.name, bol)
                    lista_caminhos_boletos.append(fs.path(filename))
                
                filename_comp = fs.save(comprovantes.name, comprovantes)
                caminho_comprovante = fs.path(filename_comp)
                
                # RETORNA O STREAMING (A tela preta com logs)
                # Passamos o 'request.user' para a função atualizar os créditos lá dentro
                response = StreamingHttpResponse(
                    processar_conciliacao_stream(lista_caminhos_boletos, caminho_comprovante, request.user)
                )
                return response

            except Exception as e:
                return HttpResponse(f"Erro: {str(e)}", status=500)
            
            # Nota: No modo streaming, o 'finally' para apagar a pasta temp é mais complexo.
            # Por enquanto, vamos deixar os arquivos temp lá e depois limpamos com cron,
            # ou o próprio script tenta limpar no final do generator.

    return render(request, 'pdf_tools/index.html')