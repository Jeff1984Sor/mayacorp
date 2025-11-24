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
from django.conf import settings

# Logger
logger = logging.getLogger(__name__)

# Configura Tesseract (Linux/Windows)
if shutil.which('tesseract'):
    pytesseract.pytesseract.tesseract_cmd = shutil.which('tesseract')
else:
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# ============================================================
# EXTRAÇÃO DE DADOS
# ============================================================

def limpar_numeros(texto):
    """Remove tudo que não é dígito."""
    if not texto: return ""
    return re.sub(r'\D', '', str(texto))

def normalizar_valor(v_str):
    """Converte string R$ 1.200,50 para float 1200.50"""
    try:
        v = str(v_str).replace('R$', '').strip()
        if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
        elif ',' in v: v = v.replace(',', '.')
        return float(v)
    except: return 0.0

def extrair_valor_nome_arquivo(nome):
    """
    Salva-vidas para PMSP: Lê '402_00' do nome do arquivo.
    """
    match = re.search(r'R\$\s?(\d+)[_.,-](\d{2})', nome)
    if match:
        try: return float(f"{match.group(1)}.{match.group(2)}")
        except: pass
    return 0.0

def regex_extrair(texto_bruto):
    """Extrai Código e Valor usando Regex."""
    dados = {'codigo': '', 'valor': 0.0}
    
    # 1. CÓDIGO: Busca sequência longa de números (36 a 60 dígitos)
    # Remove pontuação para facilitar o regex
    texto_limpo = re.sub(r'[\s\.\-\_]', '', texto_bruto)
    match_cod = re.search(r'\d{36,60}', texto_limpo)
    if match_cod:
        dados['codigo'] = match_cod.group(0) # Já retorna limpo

    # 2. VALOR: Busca formato monetário
    valores = re.findall(r'(?:R\$\s?)?(\d{1,3}(?:\.?\d{3})*,\d{2})', texto_bruto)
    floats = []
    for v in valores:
        try: floats.append(normalizar_valor(v))
        except: pass
    
    if floats:
        dados['valor'] = max(floats) # Pega o maior valor (Total)

    return dados

def extrair_inteligente(pdf_bytes, nome_arquivo=""):
    """
    Estratégia Híbrida: Texto -> OCR -> Nome do Arquivo
    """
    resultado = {'codigo': '', 'valor': 0.0, 'origem': ''}
    
    try:
        # TENTATIVA 1: TEXTO (Rápido e 100% preciso para bancos digitais)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto_pag = ""
        for page in reader.pages: texto_pag += page.extract_text() + "\n"
            
        if len(texto_pag) > 20: 
            dados = regex_extrair(texto_pag)
            if dados['valor'] > 0 or dados['codigo']:
                resultado.update(dados)
                resultado['origem'] = 'TEXTO'
                
        # TENTATIVA 2: OCR (Para imagens escaneadas/PMSP)
        # Só roda se não achou nada no texto
        if resultado['valor'] == 0 and not resultado['codigo']:
            # Converte PDF para imagem (requer poppler-utils)
            images = convert_from_bytes(pdf_bytes, dpi=200, fmt='jpeg', first_page=True)
            if images:
                texto_ocr = pytesseract.image_to_string(images[0], lang='por')
                dados = regex_extrair(texto_ocr)
                if dados['valor'] > 0 or dados['codigo']:
                    resultado.update(dados)
                    resultado['origem'] = 'OCR'

    except Exception as e:
        print(f"Erro extração: {e}")

    # TENTATIVA 3: NOME DO ARQUIVO (Último recurso para valor)
    if resultado['valor'] == 0 and nome_arquivo:
        val_nome = extrair_valor_nome_arquivo(nome_arquivo)
        if val_nome > 0:
            resultado['valor'] = val_nome
            resultado['origem'] += '+NOME'
            
    return resultado

# ============================================================
# FLUXO DE CONCILIAÇÃO
# ============================================================

def processar_reconciliacao(caminho_comprovantes, lista_caminhos_boletos, user):
    
    def emit(tipo, dados):
        return json.dumps({'type': tipo, 'data': dados}) + "\n"
    
    yield emit('log', '🚀 Iniciando (Comparação Total de Caracteres)...')

    # --- FASE 1: INVENTÁRIO DE COMPROVANTES ---
    yield emit('log', '📂 Lendo Comprovantes...')
    tabela_comprovantes = []
    
    try:
        reader_comp = PdfReader(caminho_comprovantes)
        
        for i, page in enumerate(reader_comp.pages):
            # Extrai bytes da página individual
            writer = PdfWriter()
            writer.add_page(page)
            bio = io.BytesIO()
            writer.write(bio)
            bytes_pag = bio.getvalue()
            
            # Extrai dados (Texto ou OCR)
            dados = extrair_inteligente(bytes_pag)
            
            item = {
                'id': i,
                'codigo': limpar_numeros(dados['codigo']),
                'valor': dados['valor'],
                'pdf_bytes': bytes_pag,
                'usado': False
            }
            tabela_comprovantes.append(item)
            
            # Log visual
            cod_show = f"...{item['codigo'][-10:]}" if item['codigo'] else "SEM_COD"
            msg = f"R${item['valor']} | Final: {cod_show} ({dados['origem']})"
            yield emit('comp_status', {'index': i, 'msg': msg})
            yield emit('log', f"   🧾 Comp {i+1}: {msg}")

    except Exception as e:
        yield emit('log', f"❌ Erro leitura comprovantes: {str(e)}")
        return

    # --- FASE 2: PROCESSAR BOLETOS ---
    yield emit('log', '⚡ Processando Boletos...')
    lista_final = []

    for path in lista_caminhos_boletos:
        nome_arq = os.path.basename(path)
        yield emit('file_start', {'filename': nome_arq})
        
        try:
            with open(path, 'rb') as f:
                pdf_bytes = f.read()
            
            # Extrai (Texto -> OCR -> Nome)
            dados = extrair_inteligente(pdf_bytes, nome_arq)
            
            boleto = {
                'nome': nome_arq,
                'codigo': limpar_numeros(dados['codigo']),
                'valor': dados['valor'],
                'pdf_bytes': pdf_bytes,
                'match': None,
                'motivo': ''
            }
            
            # --- MATCHING ---
            encontrado = False
            
            # 1. CÓDIGO TOTAL (CONTÉM)
            # Verifica se string A está dentro da B ou vice-versa.
            # ISSO COMPARA TODOS OS NUMEROS.
            if boleto['codigo']:
                for comp in tabela_comprovantes:
                    if comp['usado']: continue
                    if not comp['codigo']: continue
                    
                    # Logica rigorosa: Um deve conter o outro INTEIRO.
                    if boleto['codigo'] in comp['codigo'] or comp['codigo'] in boleto['codigo']:
                        boleto['match'] = comp
                        comp['usado'] = True
                        boleto['motivo'] = 'CÓDIGO EXATO'
                        encontrado = True
                        break
            
            # 2. VALOR (FILA SEQUENCIAL)
            # Se o código não bateu (ex: final diferente), cai aqui.
            if not encontrado and boleto['valor'] > 0:
                for comp in tabela_comprovantes:
                    if comp['usado']: continue
                    
                    if abs(boleto['valor'] - comp['valor']) < 0.05:
                        boleto['match'] = comp
                        comp['usado'] = True
                        boleto['motivo'] = 'VALOR (Fila)'
                        encontrado = True
                        break
            
            lista_final.append(boleto)
            
            if encontrado:
                yield emit('log', f"   ✅ {nome_arq} -> {boleto['motivo']}")
                yield emit('file_done', {'filename': nome_arq, 'status': 'success'})
            else:
                yield emit('log', f"   ❌ {nome_arq} (R${boleto['valor']}) -> Sem par")
                yield emit('file_done', {'filename': nome_arq, 'status': 'warning'})

        except Exception as e:
            yield emit('log', f"   ⚠️ Erro boleto {nome_arq}: {e}")

    # --- FASE 3: ZIP ---
    yield emit('log', '💾 Gerando Arquivo Final...')
    
    output_zip = io.BytesIO()
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for item in lista_final:
            writer_final = PdfWriter()
            
            # Boleto
            writer_final.append(io.BytesIO(item['pdf_bytes']))
            
            # Comprovante
            if item['match']:
                writer_final.append(io.BytesIO(item['match']['pdf_bytes']))
            
            bio = io.BytesIO()
            writer_final.write(bio)
            zip_file.writestr(item['nome'], bio.getvalue())

    # Finaliza
    pasta = os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(pasta, exist_ok=True)
    nome_zip = f"Conciliacao_Final_{uuid.uuid4().hex[:8]}.zip"
    
    with open(os.path.join(pasta, nome_zip), 'wb') as f:
        f.write(output_zip.getvalue())
        
    yield emit('finish', {
        'url': f"{settings.MEDIA_URL}downloads/{nome_zip}", 
        'total': len(lista_final)
    })