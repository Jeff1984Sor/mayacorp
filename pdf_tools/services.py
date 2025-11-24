import io
import os
import zipfile
import uuid
import json
import re
import logging
import shutil
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
from django.conf import settings
from django.core.cache import cache

# Configura logger
logger = logging.getLogger(__name__)

# Configura Tesseract no Linux
if shutil.which('tesseract'):
    pytesseract.pytesseract.tesseract_cmd = shutil.which('tesseract')
else:
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# ============================================================
# FERRAMENTAS DE LIMPEZA
# ============================================================

def limpar_numeros(texto):
    """Retorna apenas dígitos de uma string."""
    if not texto: return ""
    return re.sub(r'\D', '', str(texto))

def normalizar_valor(valor_str):
    """Converte '1.200,50' ou '1200.50' para float."""
    try:
        if isinstance(valor_str, (int, float)): return float(valor_str)
        v = str(valor_str).replace('R$', '').strip()
        if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.') # 1.000,00 -> 1000.00
        elif ',' in v: v = v.replace(',', '.') # 100,00 -> 100.00
        return float(v)
    except: return 0.0

def formatar_br(valor):
    return f"{valor:,.2f}".replace('.', 'X').replace(',', '.').replace('X', ',')

# ============================================================
# EXTRAÇÃO INTELIGENTE (TEXTO -> OCR -> NOME)
# ============================================================

def extrair_valor_nome(nome):
    """Lê valor do nome do arquivo (Salva-vidas)."""
    # Procura 402_00, 402-00 ou 402,00
    match = re.search(r'R\$\s?(\d+)[_.,-](\d{2})', nome)
    if match:
        try: return float(f"{match.group(1)}.{match.group(2)}")
        except: pass
    return 0.0

def regex_busca_dados(texto_bruto):
    """Aplica Regex num texto qualquer (vindo do PDF ou do OCR)."""
    dados = {'codigo': '', 'valor': 0.0, 'empresa': 'N/A'}
    
    # 1. CÓDIGO (Busca sequencia de 36 a 48 digitos)
    # Remove espaços e pontos para facilitar a busca
    texto_limpo = re.sub(r'[\s\.\-\_]', '', texto_bruto)
    match_cod = re.search(r'\d{36,48}', texto_limpo)
    if match_cod:
        dados['codigo'] = match_cod.group(0)

    # 2. VALOR (Busca formato monetário)
    valores = re.findall(r'(?:R\$\s?)?(\d{1,3}(?:\.?\d{3})*,\d{2})', texto_bruto)
    floats = []
    for v in valores:
        try: floats.append(normalizar_valor(v))
        except: pass
    if floats:
        dados['valor'] = max(floats) # Pega o maior valor (Total)

    # 3. EMPRESA (Busca simples por palavras chaves)
    if "PREFEITURA" in texto_bruto.upper() or "MUNICIPAL" in texto_bruto.upper():
        dados['empresa'] = "PREFEITURA"
    elif "CYRELA" in texto_bruto.upper():
        dados['empresa'] = "CYRELA"
    
    return dados

def extrair_hibrido(pdf_bytes, nome_arquivo=""):
    """
    Tenta todas as estratégias possíveis.
    1. Texto do PDF (Rápido e Preciso)
    2. OCR (Lento, para imagens)
    3. Nome do Arquivo (Fallback para valor)
    """
    resultado = {'codigo': '', 'valor': 0.0, 'origem': ''}
    
    try:
        # TENTATIVA 1: LER TEXTO (Ideal para Comprovantes Itaú/Bradesco)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto_pag = ""
        for page in reader.pages:
            texto_pag += page.extract_text() + "\n"
            
        if len(texto_pag) > 50: # Se extraiu texto decente
            dados = regex_busca_dados(texto_pag)
            if dados['valor'] > 0 or dados['codigo']:
                resultado.update(dados)
                resultado['origem'] = 'TEXTO'
                
        # TENTATIVA 2: OCR (Só se texto falhou)
        if resultado['valor'] == 0 and not resultado['codigo']:
            # Converte para imagem
            images = convert_from_bytes(pdf_bytes, dpi=200, fmt='jpeg', first_page=True)
            if images:
                texto_ocr = pytesseract.image_to_string(images[0], lang='por')
                dados = regex_busca_dados(texto_ocr)
                if dados['valor'] > 0 or dados['codigo']:
                    resultado.update(dados)
                    resultado['origem'] = 'OCR'

    except Exception as e:
        print(f"Erro na extração: {e}")

    # TENTATIVA 3: NOME DO ARQUIVO (Último recurso para valor)
    if resultado['valor'] == 0 and nome_arquivo:
        val_nome = extrair_valor_nome(nome_arquivo)
        if val_nome > 0:
            resultado['valor'] = val_nome
            if not resultado['origem']: resultado['origem'] = 'NOME_ARQ'
            else: resultado['origem'] += '+NOME'
            
    return resultado

# ============================================================
# FLUXO PRINCIPAL
# ============================================================

def processar_reconciliacao(caminho_comprovantes, lista_caminhos_boletos, user):
    
    def emit(tipo, dados):
        return json.dumps({'type': tipo, 'data': dados}) + "\n"
    
    yield emit('log', '🚀 Iniciando Processamento Híbrido (Texto + OCR + Nome)...')

    # --- LISTA 1: COMPROVANTES (TABELA VIRTUAL) ---
    yield emit('log', '📂 Lendo Comprovantes...')
    tabela_comprovantes = []
    
    try:
        # Lê o PDFzão de comprovantes
        reader_comp = PdfReader(caminho_comprovantes)
        total_pags = len(reader_comp.pages)
        
        for i, page in enumerate(reader_comp.pages):
            # Extrai página individual
            writer = PdfWriter()
            writer.add_page(page)
            bio = io.BytesIO()
            writer.write(bio)
            bytes_pag = bio.getvalue()
            
            # Extrai dados (Sem nome de arquivo, pois é um paginadão)
            dados = extrair_hibrido(bytes_pag)
            
            item = {
                'id': i,
                'codigo': limpar_numeros(dados['codigo']),
                'valor': dados['valor'],
                'pdf_bytes': bytes_pag,
                'usado': False
            }
            tabela_comprovantes.append(item)
            
            # Log Visual
            cod_show = f"...{item['codigo'][-6:]}" if item['codigo'] else "SEM_COD"
            yield emit('comp_status', {'index': i, 'msg': f"R${item['valor']} ({dados['origem']})"})
            yield emit('log', f"   🧾 Pág {i+1}: R${formatar_br(item['valor'])} | Cod: {cod_show} | Via: {dados['origem']}")

    except Exception as e:
        yield emit('log', f"❌ Erro fatal lendo comprovantes: {str(e)}")
        return

    # --- LISTA 2: BOLETOS ---
    yield emit('log', '⚡ Processando Boletos...')
    lista_boletos_processados = []

    for path in lista_caminhos_boletos:
        nome_arq = os.path.basename(path)
        yield emit('file_start', {'filename': nome_arq})
        
        try:
            with open(path, 'rb') as f:
                pdf_bytes = f.read()
            
            # Extrai dados (passando nome do arquivo para fallback)
            dados = extrair_hibrido(pdf_bytes, nome_arq)
            
            boleto = {
                'nome': nome_arq,
                'codigo': limpar_numeros(dados['codigo']),
                'valor': dados['valor'],
                'pdf_bytes': pdf_bytes,
                'match': None,
                'motivo': ''
            }
            
            # --- TENTATIVA DE MATCH ---
            match_ok = False
            
            # 1. POR CÓDIGO (Contém ou Igual)
            if boleto['codigo']:
                for comp in tabela_comprovantes:
                    if comp['usado']: continue
                    if not comp['codigo']: continue
                    
                    # Verifica se um está contido no outro (resolve digitos verificadores)
                    if boleto['codigo'] in comp['codigo'] or comp['codigo'] in boleto['codigo']:
                        boleto['match'] = comp
                        comp['usado'] = True
                        boleto['motivo'] = 'CÓDIGO'
                        match_ok = True
                        break
            
            # 2. POR VALOR (Fila Sequencial)
            if not match_ok and boleto['valor'] > 0:
                for comp in tabela_comprovantes:
                    if comp['usado']: continue
                    
                    if abs(boleto['valor'] - comp['valor']) < 0.05:
                        boleto['match'] = comp
                        comp['usado'] = True
                        boleto['motivo'] = 'VALOR'
                        match_ok = True
                        break
            
            lista_boletos_processados.append(boleto)
            
            # Feedback
            if match_ok:
                yield emit('log', f"   ✅ {nome_arq} -> Match por {boleto['motivo']}")
                yield emit('file_done', {'filename': nome_arq, 'status': 'success'})
            else:
                yield emit('log', f"   ❌ {nome_arq} (R${boleto['valor']}) -> Sem par")
                yield emit('file_done', {'filename': nome_arq, 'status': 'warning'})

        except Exception as e:
            yield emit('log', f"   ⚠️ Erro ao ler {nome_arq}: {e}")

    # --- ETAPA 3: ZIP ---
    yield emit('log', '💾 Gerando Arquivo Final...')
    
    output_zip = io.BytesIO()
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for item in lista_boletos_processados:
            writer_final = PdfWriter()
            
            # Boleto
            writer_final.append(io.BytesIO(item['pdf_bytes']))
            
            # Comprovante (se tiver)
            if item['match']:
                writer_final.append(io.BytesIO(item['match']['pdf_bytes']))
            
            bio = io.BytesIO()
            writer_final.write(bio)
            zip_file.writestr(item['nome'], bio.getvalue())

    # Salva
    pasta = os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(pasta, exist_ok=True)
    nome_zip = f"Conciliacao_Hibrida_{uuid.uuid4().hex[:8]}.zip"
    
    with open(os.path.join(pasta, nome_zip), 'wb') as f:
        f.write(output_zip.getvalue())
        
    yield emit('finish', {
        'url': f"{settings.MEDIA_URL}downloads/{nome_zip}", 
        'total': len(lista_boletos_processados)
    })