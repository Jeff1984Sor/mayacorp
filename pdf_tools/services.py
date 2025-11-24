import io
import os
import zipfile
import time
import uuid
import json
import re
from unidecode import unidecode # pip install unidecode
from pypdf import PdfReader, PdfWriter
import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GOOGLE_API_KEY)

# --- FUNÇÕES UTILITÁRIAS ---

def limpar_apenas_numeros(texto):
    if not texto: return ""
    return re.sub(r'\D', '', str(texto))

def normalizar_nome(nome):
    """Limpa nome para comparação."""
    if not nome: return ""
    nome = nome.upper().replace('.', ' ').replace('-', ' ').replace('/', ' ')
    try: nome = unidecode(nome)
    except: pass
    
    ignorar = ['LTDA', 'S.A.', 'S/A', 'ME', 'EPP', 'BANCO', 'PAGAMENTO', 'BOLETO', 'MUNICIPIO', 'PREFEITURA']
    palavras = [p for p in nome.split() if p not in ignorar and len(p) > 2]
    return " ".join(palavras)

def sao_nomes_parecidos(nome1, nome2):
    n1 = normalizar_nome(nome1)
    n2 = normalizar_nome(nome2)
    if not n1 or not n2: return False
    if n1 in n2 or n2 in n1: return True
    # Compara primeira palavra relevante (Ex: CYRELA)
    p1 = n1.split()[0] if n1 else ""
    p2 = n2.split()[0] if n2 else ""
    if p1 == p2 and len(p1) > 3: return True
    return False

def extrair_regex_rapido(texto):
    """Tenta extrair código e valor instantaneamente via Regex."""
    dados = {'codigo_limpo': '', 'valor': 0.0, 'sucesso': False}
    
    # 1. Código
    texto_limpo = texto.replace('\n', '').replace(' ', '').replace('.', '').replace('-', '')
    match_cod = re.search(r'\d{44,48}', texto_limpo)
    if match_cod:
        dados['codigo_limpo'] = match_cod.group(0)
        dados['sucesso'] = True # Se achou código, consideramos sucesso
    
    # 2. Valor (Tentativa simples)
    match_val = re.search(r'R\$\s?([\d\.,]+)', texto)
    if match_val:
        try:
            val_str = match_val.group(1).replace('.', '').replace(',', '.')
            dados['valor'] = float(val_str)
        except: pass
        
    return dados

def chamar_ia_completa(texto, tipo_doc):
    """Extrai tudo: Valor, Codigo e EMPRESA."""
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""
    Analise este {tipo_doc}. Extraia JSON:
    {{ "valor": float, "codigo_barras": "string", "empresa": "Nome do Beneficiario/Cedente" }}
    Texto: {texto[:4000]}
    """
    for _ in range(2):
        try:
            resp = model.generate_content(prompt)
            clean = resp.text.replace('```json', '').replace('```', '').strip()
            d = json.loads(clean)
            d['codigo_limpo'] = limpar_apenas_numeros(d.get('codigo_barras'))
            d['valor'] = float(d.get('valor') or 0)
            return d
        except: time.sleep(0.5)
    return {"valor": 0.0, "codigo_limpo": "", "empresa": ""}

# --- FLUXO PRINCIPAL ---

def processar_conciliacao_json_stream(lista_caminhos_boletos, caminho_comprovantes, user):
    
    def send(type, data):
        return json.dumps({'type': type, 'data': data}) + "\n"

    nomes_boletos = [os.path.basename(p) for p in lista_caminhos_boletos]
    yield send('init_list', {'files': nomes_boletos})
    yield send('log', '🚀 Iniciando Conciliação Híbrida (Velocidade + Precisão)...')

    total_paginas = 0
    comprovantes_map = []

    # ==========================================
    # 1. PREPARAR COMPROVANTES (Necessário IA para pegar Empresa)
    # ==========================================
    yield send('log', '📂 Indexando comprovantes...')
    
    reader_comp = PdfReader(caminho_comprovantes)
    total_paginas += len(reader_comp.pages)
    
    for i, page in enumerate(reader_comp.pages):
        texto = page.extract_text() or ""
        
        # Aqui usamos IA porque precisamos do NOME DA EMPRESA para o desempate
        # O modelo Flash é rápido (< 1s)
        yield send('comp_status', {'index': i, 'msg': 'Indexando dados...'})
        dados = chamar_ia_completa(texto, "comprovante")
        
        # Prepara PDF
        writer = PdfWriter()
        writer.add_page(page)
        pdf_bytes = io.BytesIO()
        writer.write(pdf_bytes)
        pdf_bytes.seek(0)
        
        comprovantes_map.append({
            'page_obj': pdf_bytes,
            'dados': dados,
            'usado': False
        })
        # Print Debug
        emp = (dados.get('empresa') or '')[:10]
        print(f"COMP {i}: R${dados['valor']} | Cod:{dados['codigo_limpo'][:6]}... | {emp}", flush=True)

    # ==========================================
    # 2. PROCESSAR BOLETOS (Híbrido: Regex -> IA)
    # ==========================================
    yield send('log', '⚡ Processando Boletos...')
    
    output_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(output_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        for boleto_path in lista_caminhos_boletos:
            nome_arquivo = os.path.basename(boleto_path)
            yield send('file_start', {'filename': nome_arquivo})
            
            # Leitura
            reader_bol = PdfReader(boleto_path)
            texto_bol = ""
            for p in reader_bol.pages: texto_bol += p.extract_text() or ""
            total_paginas += len(reader_bol.pages)

            # --- ESTRATÉGIA DE VELOCIDADE ---
            # 1. Tenta REGEX (Instantâneo)
            dados_bol = extrair_regex_rapido(texto_bol)
            origem = "REGEX"
            
            # 2. Se o Regex falhou no código, chama IA
            if not dados_bol['sucesso']:
                dados_bol = chamar_ia_completa(texto_bol, "boleto")
                origem = "IA"
            
            cod_bol = dados_bol.get('codigo_limpo')
            val_bol = dados_bol.get('valor')
            # Empresa só existe se veio da IA, senão string vazia
            emp_bol = dados_bol.get('empresa', '')

            print(f"BOLETO {nome_arquivo}: {origem} | Cod:{cod_bol[:10]}... | R${val_bol}", flush=True)

            # --- MATCHING ---
            match = None
            motivo = ""

            # NÍVEL 1: CÓDIGO (Prioridade)
            if cod_bol and len(cod_bol) > 20:
                for comp in comprovantes_map:
                    if comp['usado']: continue
                    c_cod = comp['dados']['codigo_limpo']
                    if c_cod and (cod_bol == c_cod or cod_bol.startswith(c_cod[:20]) or c_cod.startswith(cod_bol[:20])):
                        match = comp
                        motivo = "CÓDIGO"
                        break
            
            # NÍVEL 2: VALOR + EMPRESA (Se falhou o código)
            if not match and val_bol > 0:
                # Se não temos o nome da empresa do boleto (pq veio do regex),
                # precisamos chamar a IA AGORA para pegar o nome
                if not emp_bol:
                    yield send('log', f'🔎 Buscando empresa no boleto: {nome_arquivo}')
                    dados_ia_extra = chamar_ia_completa(texto_bol, "boleto")
                    emp_bol = dados_ia_extra.get('empresa', '')
                
                if emp_bol:
                    for comp in comprovantes_map:
                        if comp['usado']: continue
                        if abs(val_bol - comp['dados']['valor']) < 0.05:
                            if sao_nomes_parecidos(emp_bol, comp['dados'].get('empresa', '')):
                                match = comp
                                motivo = f"VALOR+EMPRESA ({emp_bol})"
                                break
            
            # NÍVEL 3: SÓ VALOR (Último recurso, se único)
            if not match and val_bol > 0:
                 for comp in comprovantes_map:
                    if comp['usado']: continue
                    if abs(val_bol - comp['dados']['valor']) < 0.01:
                        match = comp
                        motivo = "APENAS VALOR (Aviso)"
                        break

            # GERA PDF
            writer_final = PdfWriter()
            temp_reader = PdfReader(boleto_path)
            for p in temp_reader.pages: writer_final.add_page(p)
            
            status_ui = 'warning'
            if match:
                match['usado'] = True
                status_ui = 'success'
                reader_m = PdfReader(match['page_obj'])
                writer_final.add_page(reader_m.pages[0])
                yield send('log', f'✅ Match ({motivo}): {nome_arquivo}')
            else:
                yield send('log', f'❌ Sem comprovante: {nome_arquivo}')

            pdf_out = io.BytesIO()
            writer_final.write(pdf_out)
            zip_file.writestr(nome_arquivo, pdf_out.getvalue())
            
            yield send('file_done', {'filename': nome_arquivo, 'status': status_ui})

    # FINALIZA
    pasta_downloads = os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(pasta_downloads, exist_ok=True)
    nome_zip = f"Conciliacao_Final_{uuid.uuid4().hex[:8]}.zip"
    with open(os.path.join(pasta_downloads, nome_zip), "wb") as f:
        f.write(output_zip_buffer.getvalue())

    if hasattr(user, 'paginas_processadas'):
        user.paginas_processadas += total_paginas
        user.save()

    yield send('finish', {'url': f"{settings.MEDIA_URL}downloads/{nome_zip}", 'total': total_paginas})