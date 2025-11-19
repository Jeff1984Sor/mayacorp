from django.shortcuts import render
from django.http import HttpResponse
from core.decorators import possui_produto  # <--- IMPORTAR O NOVO
from .services import processar_conciliacao
import zipfile
from datetime import datetime
from django.contrib.auth.decorators import login_required

@possui_produto('gerador-pdf')
@login_required # Garante que request.user existe
def gerador_home(request):
    if request.method == "POST":
        boletos = request.FILES.getlist('boletos')
        comprovantes = request.FILES.get('comprovantes')
        
        if boletos and comprovantes:
            # AGORA A FUNÇÃO RETORNA DUAS COISAS
            zip_buffer, qtd_paginas = processar_conciliacao(boletos, comprovantes)
            
            # --- ATUALIZA O USUÁRIO ---
            request.user.paginas_processadas += qtd_paginas
            request.user.save()
            
            # Pega a data de hoje
            hoje = datetime.now().strftime("%d-%m-%Y")
            nome_do_zip = f"Boletos + Comprovantes - {hoje}.zip"
            
            response = HttpResponse(zip_buffer, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{nome_do_zip}"'
            return response

    return render(request, 'pdf_tools/index.html')