import io
import os
import zipfile
import uuid
import json
import re
import logging
from difflib import SequenceMatcher
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes # Requer poppler-utils instalado no Linux
from PIL import Image
import google.generativeai as genai
from django.conf import settings

# Logger
logger = logging.getLogger(__name__)

# Configura Google AI
genai.configure(api_key=settings.GOOGLE_API_KEY)

# ============================================================
# FERRAMENTAS MATEMÁTICAS
# ============================================================

def calcular_similaridade(a, b):
    """Nota de 0.0 a 1.0 de semelhança."""
    if not a or not b: return 0.0
    return SequenceMatcher(None, a, b).ratio()

def limpar_numeros(texto):
    """Deixa só numeros."""
    if not texto: return ""
    return re.sub(r'\D', '', str(texto))

def normalizar_valor(v_str):
    try:
        v = str(v_str).replace('R$', '').strip()
        if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
        elif ',' in v: v = v.replace(',', '.')
        return float(v)
    except: return 0.0

def extrair_valor_nome(nome):
    """Salva-vidas: Lê '402_00' do nome do arquivo."""
    match = re.search(r'R\$\s?(\d+)[_.,-](\d{2})', nome)
    if match:
        try: return float(f"{match.group(1)}.{match.group(2)}")
        except: pass
    return 0.0

# ============================================================
# EXTRAÇÃO COM GEMINI VISION (O PULO DO GATO 🐈)
# ============================================================

def extrair_com_gemini_vision(pdf_bytes, tipo_doc, nome_arquivo=""):
    """
    Converte PDF em Imagem e manda para o Gemini 1.5 Flash.
    Ele 'olha' o documento e extrai os dados com precisão humana.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    try:
        # 1. Converte 1ª página do PDF para Imagem
        # (Isso resolve o problema de PDFs escaneados/imagem)
        imagens = convert_from_bytes(pdf_bytes, first_page=True, dpi=200, fmt='jpeg')
        if not imagens:
            return {'codigo': '', 'valor': 0.0, 'origem': 'FALHA_IMG'}
            
        imagem_pil = imagens[0]

        # 2. Pergunta para a IA
        prompt = f"""
        Você é um sistema financeiro. Analise esta imagem de um {tipo_doc}.
        Extraia EXATAMENTE:
        1. O Valor Total do documento (float).
        2. A Linha Digitável ou Código de Barras numérico.
           - Se for boleto bancário, geralmente começa com o código do banco.
           - Se for imposto/prefeitura (DAMSP), geralmente começa com 8.
           - Copie TODOS os números visíveis do código de barras, sem perder nenhum.
        
        Retorne APENAS JSON: {{ "valor": 0.00, "codigo": "apenas_numeros" }}
        """

        # Envia Imagem + Texto
        response = model.generate_content([prompt, imagem_pil])
        
        # 3. Processa Resposta
        texto_resp = response.text.replace('```json', '').replace('```', '').strip()
        dados = json.loads(texto_resp)
        
        return {
            'codigo': limpar_numeros(dados.get('codigo')),
            'valor': normalizar_valor(dados.get('valor')),
            'origem': 'GEMINI_VISION'
        }

    except Exception as e:
        print(f"Erro Gemini Vision: {e}")
        # Fallback: Se a IA falhar, tenta pegar valor do nome do arquivo
        val_nome = extrair_valor_nome(nome_arquivo)
        return {'codigo': '', 'valor': val_nome, 'origem': 'ERRO_IA'}

# ============================================================
# FLUXO PRINCIPAL
# ============================================================

def processar_reconciliacao(caminho_comprovantes, lista_caminhos_boletos, user):
    
    def emit(tipo, dados):
        return json.dumps({'type': tipo, 'data': dados}) + "\n"
    
    yield emit('log', '🚀 Iniciando com GEMINI VISION (IA Visual)...')

    # --- 1. LER COMPROVANTES ---
    yield emit('log', '📸 Fotografando Comprovantes...')
    pool_comprovantes = []
    
    try:
        reader = PdfReader(caminho_comprovantes)
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            bio = io.BytesIO()
            writer.write(bio)
            b_pag = bio.getvalue()
            
            # Manda a imagem pro Google ler
            d = extrair_com_gemini_vision(b_pag, "comprovante de pagamento bancario")
            
            item = {
                'id': i,
                'codigo': d['codigo'],
                'valor': d['valor'],
                'pdf_bytes': b_pag,
                'usado': False
            }
            pool_comprovantes.append(item)
            
            show_cod = f"...{item['codigo'][-6:]}" if item['codigo'] else "SEM_COD"
            yield emit('comp_status', {'index': i, 'msg': f"R${item['valor']} ({show_cod})"})
            yield emit('log', f"   🧾 Comp {i+1}: R${item['valor']} | {show_cod}")

    except Exception as e:
        yield emit('log', f"❌ Erro leitura: {e}")
        return

    # --- 2. LER BOLETOS E COMPARAR ---
    yield emit('log', '⚡ Analisando Boletos (Visão Computacional)...')
    lista_final = []

    for path in lista_caminhos_boletos:
        nome = os.path.basename(path)
        yield emit('file_start', {'filename': nome})
        
        try:
            with open(path, 'rb') as f: pdf_bytes = f.read()
            
            # Manda a imagem pro Google ler
            d = extrair_com_gemini_vision(pdf_bytes, "boleto/guia de imposto", nome)
            
            boleto = {
                'nome': nome,
                'codigo': d['codigo'],
                'valor': d['valor'],
                'pdf_bytes': pdf_bytes,
                'match': None,
                'motivo': ''
            }
            
            # === MATCH POR SIMILARIDADE ===
            melhor_candidato = None
            maior_nota = 0.0
            
            if boleto['valor'] > 0:
                # 1. Filtra por VALOR IGUAL
                candidatos = [c for c in pool_comprovantes if not c['usado'] and abs(c['valor'] - boleto['valor']) < 0.05]
                
                if candidatos:
                    # 2. Dentre os de mesmo valor, qual tem código mais parecido?
                    for cand in candidatos:
                        nota = calcular_similaridade(boleto['codigo'], cand['codigo'])
                        if nota > maior_nota:
                            maior_nota = nota
                            melhor_candidato = cand
                    
                    # 3. Regras de Aceite
                    aceito = False
                    
                    # Se código muito parecido (>60%)
                    if maior_nota > 0.6:
                        aceito = True
                        boleto['motivo'] = f"SIMILARIDADE ({int(maior_nota*100)}%)"
                    
                    # Se código ruim/inexistente, mas só tem 1 opção de valor
                    elif len(candidatos) == 1:
                        aceito = True
                        boleto['motivo'] = "VALOR (Único)"
                        
                    if aceito and melhor_candidato:
                        boleto['match'] = melhor_candidato
                        melhor_candidato['usado'] = True
                        yield emit('log', f"   ✅ {nome} -> {boleto['motivo']}")
                        yield emit('file_done', {'filename': nome, 'status': 'success'})
                    else:
                         yield emit('log', f"   ⚠️ {nome} (R${boleto['valor']}) -> Código muito diferente.")
                         yield emit('file_done', {'filename': nome, 'status': 'warning'})

                else:
                    yield emit('log', f"   ❌ {nome} (R${boleto['valor']}) -> Sem comprovante deste valor.")
                    yield emit('file_done', {'filename': nome, 'status': 'warning'})
            else:
                yield emit('log', f"   ❌ {nome} -> Valor Zero/Ilegível")
                yield emit('file_done', {'filename': nome, 'status': 'warning'})
                
            lista_final.append(boleto)

        except Exception as e:
            yield emit('log', f"⚠️ Erro: {e}")

    # --- 3. ZIP ---
    yield emit('log', '💾 Gerando Zip...')
    output_zip = io.BytesIO()
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for item in lista_final:
            w = PdfWriter()
            w.append(io.BytesIO(item['pdf_bytes']))
            if item['match']:
                w.append(io.BytesIO(item['match']['pdf_bytes']))
            bio = io.BytesIO()
            w.write(bio)
            zip_file.writestr(item['nome'], bio.getvalue())

    # Finaliza
    pasta = os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(pasta, exist_ok=True)
    nome_zip = f"Conciliacao_Vision_{uuid.uuid4().hex[:8]}.zip"
    with open(os.path.join(pasta, nome_zip), 'wb') as f: f.write(output_zip.getvalue())
        
    yield emit('finish', {'url': f"{settings.MEDIA_URL}downloads/{nome_zip}", 'total': len(lista_final)})