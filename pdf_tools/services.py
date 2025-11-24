import io
import os
import zipfile
import time
import uuid
import json
import re
from pypdf import PdfReader, PdfWriter
from django.conf import settings

# --- FERRAMENTAS ---

def limpar_numeros(texto):
    """Deixa só numeros. Ex: '816-2.0' -> '81620'"""
    if not texto: return ""
    return re.sub(r'\D', '', str(texto))

def extrair_dados_regex(texto, nome_arquivo=""):
    """
    Extrai Código e Valor na força bruta (Regex).
    Se o valor falhar no texto, tenta pegar do nome do arquivo (ex: 'Boleto_402_00.pdf')
    """
    dados = {'codigo': '', 'valor': 0.0}
    
    # 1. Código (Procura sequencias longas)
    texto_limpo = texto.replace('\n', '').replace(' ', '').replace('.', '').replace('-', '')
    match_cod = re.search(r'\d{36,}', texto_limpo) # Pelo menos 36 digitos juntos
    if match_cod:
        dados['codigo'] = match_cod.group(0)
        
    # 2. Valor no Texto
    # Procura formato 1.000,00 ou 100,00
    valores = re.findall(r'(?:R\$\s?)?(\d{1,3}(?:\.?\d{3})*,\d{2})', texto)
    floats = []
    for v in valores:
        try: floats.append(float(v.replace('.', '').replace(',', '.')))
        except: pass
    
    if floats:
        dados['valor'] = max(floats) # Assume o maior valor da página
        
    # 3. Salva-Vidas: Valor no Nome do Arquivo (Para o caso PMSP)
    if dados['valor'] == 0 and nome_arquivo:
        # Procura '402_00' ou '402,00' no nome
        match_nome = re.search(r'R\$\s?(\d+)[_,.](\d{2})', nome_arquivo)
        if match_nome:
            try:
                dados['valor'] = float(f"{match_nome.group(1)}.{match_nome.group(2)}")
            except: pass
            
    return dados

def checar_match_ultimos_20(cod_a, cod_b):
    """A Lógica de Ouro: Compara os últimos 20 dígitos."""
    if not cod_a or not cod_b: return False
    
    # Garante que tem pelo menos 20 digitos para comparar
    if len(cod_a) < 20 or len(cod_b) < 20:
        # Se for curto, tenta match exato
        return cod_a == cod_b
    
    # Pega os ultimos 20
    final_a = cod_a[-20:]
    final_b = cod_b[-20:]
    
    return final_a == final_b

# --- PROCESSAMENTO ---

def processar_conciliacao_json_stream(lista_caminhos_boletos, caminho_comprovantes, user):
    
    def send(type, data):
        return json.dumps({'type': type, 'data': data}) + "\n"

    yield send('init_list', {'files': [os.path.basename(p) for p in lista_caminhos_boletos]})
    yield send('log', '🚀 Iniciando Lógica: "Últimos 20 Dígitos"...')

    # Tabela Virtual de Comprovantes
    tabela_comprovantes = []
    
    # 1. LER COMPROVANTES
    yield send('log', '📂 Lendo Comprovantes...')
    reader_comp = PdfReader(caminho_comprovantes)
    
    for i, page in enumerate(reader_comp.pages):
        texto = page.extract_text() or ""
        dados = extrair_dados_regex(texto)
        
        # Salva binário da página
        writer = PdfWriter()
        writer.add_page(page)
        bio = io.BytesIO()
        writer.write(bio)
        
        item = {
            'id': i,
            'origem': f"Pag {i+1}",
            'codigo': limpar_numeros(dados['codigo']),
            'valor': dados['valor'],
            'pdf_bytes': bio,
            'usado': False
        }
        tabela_comprovantes.append(item)
        
        # Mostra os ultimos 20 no log para conferencia
        final_cod = item['codigo'][-20:] if len(item['codigo']) > 20 else item['codigo']
        yield send('comp_status', {'index': i, 'msg': f"R${item['valor']} | ...{final_cod}"})

    # 2. LER BOLETOS E MATCH IMEDIATO
    yield send('log', '⚡ Comparando Boletos...')
    
    resultados = [] # Lista final para o ZIP
    
    for path in lista_caminhos_boletos:
        nome_arq = os.path.basename(path)
        yield send('file_start', {'filename': nome_arq})
        
        reader = PdfReader(path)
        texto = ""
        for p in reader.pages: texto += p.extract_text() or ""
        
        # Extrai dados (incluindo o truque do nome do arquivo)
        dados = extrair_dados_regex(texto, nome_arq)
        cod_boleto = limpar_numeros(dados['codigo'])
        val_boleto = dados['valor']
        
        with open(path, 'rb') as f: bio = io.BytesIO(f.read())
        
        boleto_struct = {
            'nome': nome_arq,
            'pdf_bytes': bio,
            'match_obj': None,
            'motivo': ''
        }

        # --- LÓGICA DE MATCH ---
        
        # 1. Tenta pelos ÚLTIMOS 20 DIGITOS
        match_found = False
        if cod_boleto:
            for comp in tabela_comprovantes:
                if comp['usado']: continue
                
                if checar_match_ultimos_20(cod_boleto, comp['codigo']):
                    match_found = True
                    comp['usado'] = True
                    boleto_struct['match_obj'] = comp
                    boleto_struct['motivo'] = f"CÓDIGO (...{cod_boleto[-20:]})"
                    break
        
        # 2. Se falhar, tenta pelo VALOR (Fila Indiana)
        if not match_found and val_boleto > 0:
            for comp in tabela_comprovantes:
                if comp['usado']: continue
                
                if abs(val_boleto - comp['valor']) < 0.05:
                    match_found = True
                    comp['usado'] = True
                    boleto_struct['match_obj'] = comp
                    boleto_struct['motivo'] = f"VALOR (R$ {val_boleto})"
                    break
        
        # Log e Feedback Visual
        if match_found:
            yield send('log', f"✅ {nome_arq} -> {boleto_struct['motivo']}")
            yield send('file_done', {'filename': nome_arq, 'status': 'success'})
        else:
            yield send('log', f"❌ {nome_arq} (R${val_boleto}) -> Sem par.")
            yield send('file_done', {'filename': nome_arq, 'status': 'warning'})
            
        resultados.append(boleto_struct)

    # 3. GERAR ZIP
    yield send('log', '💾 Criando arquivo final...')
    
    output_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(output_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for item in resultados:
            writer_final = PdfWriter()
            
            # Adiciona Boleto
            item['pdf_bytes'].seek(0)
            rb = PdfReader(item['pdf_bytes'])
            for p in rb.pages: writer_final.add_page(p)
            
            # Adiciona Comprovante (se tiver)
            if item['match_obj']:
                item['match_obj']['pdf_bytes'].seek(0)
                rc = PdfReader(item['match_obj']['pdf_bytes'])
                writer_final.add_page(rc.pages[0])
            
            # Salva
            bio = io.BytesIO()
            writer_final.write(bio)
            zip_file.writestr(item['nome'], bio.getvalue())
            
    # Finaliza
    pasta = os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(pasta, exist_ok=True)
    nome_zip = f"Conciliacao_20Dig_{uuid.uuid4().hex[:8]}.zip"
    
    with open(os.path.join(pasta, nome_zip), "wb") as f:
        f.write(output_zip_buffer.getvalue())

    total_paginas = len(tabela_comprovantes) + len(resultados)
    if hasattr(user, 'paginas_processadas'):
        user.paginas_processadas += total_paginas
        user.save()

    yield send('finish', {'url': f"{settings.MEDIA_URL}downloads/{nome_zip}", 'total': total_paginas})