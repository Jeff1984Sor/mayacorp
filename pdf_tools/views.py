from django.shortcuts import render
from django.http import HttpResponse
from core.decorators import possui_produto  # <--- IMPORTAR O NOVO
from .services import processar_conciliacao
from datetime import datetime

@possui_produto('gerador-pdf') 
def gerador_home(request):
    if request.method == "POST":
        boletos = request.FILES.getlist('boletos')
        comprovantes = request.FILES.get('comprovantes')
        
        if boletos and comprovantes:
            # Processa o ZIP
            zip_buffer = processar_conciliacao(boletos, comprovantes)
            
            # Pega a data de hoje formatada (Dia-Mes-Ano)
            hoje = datetime.now().strftime("%d-%m-%Y")
            nome_do_zip = f"Boletos + Comprovantes - {hoje}.zip"
            
            # Configura o download
            response = HttpResponse(zip_buffer, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{nome_do_zip}"'
            
            return response

    return render(request, 'pdf_tools/index.html')