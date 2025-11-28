import io
import os
import zipfile
import uuid
import json
import re
import logging
import time
import fitz  # PyMuPDF
from difflib import SequenceMatcher
from pypdf import PdfReader, PdfWriter
from PIL import Image
import google.generativeai as genai
from google.generativeai.types import RequestOptions
from django.conf import settings

# Configuração do logger
logger = logging.getLogger(__name__)

# Configura a API do Google Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)

# ============================================================
# FERRAMENTAS AUXILIARES
# ============================================================

def limpar_numeros(texto):
    return re.sub(r'\D', '', str(texto or ""))

def calcular_similaridade(a, b):
    if not a or not b: return 0.0
    return SequenceMatcher(None, a, b).ratio()

def normalizar_valor(v_str):
    try:
        if isinstance(v_str, (float, int)): return float(v_str)
        v = str(v_str).replace('R$', '').strip()
        if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
        elif ',' in v: v = v.replace(',', '.')
        return float(v)
    except (ValueError, TypeError):
        return 0.0

def extrair_valor_nome(nome_arquivo):
    match = re.search(r'R\$\s?(\d+)[_.,-](\d{2})', nome_arquivo)
    if match:
        try:
            return float(f"{match.group(1)}.{match.group(2)}")
        except:
            pass
    return 0.0

# ============================================================
# FUNÇÃO DA IA GEMINI (OTIMIZADA)
# ============================================================

def chamar_gemini_imagem(imagem_pil, tipo_doc):
    """
    Envia imagem para a Gemini com timeout estendido e retry inteligente.
    """
    model = genai.GenerativeModel('gemini-1.5-flash') # Modelo mais rápido
    
    prompt = f"""
    Analise esta imagem de um {tipo_doc}.
    TAREFA:
    1. VALOR TOTAL: Encontre o valor monetário total.
    2. CÓDIGO DE BARRAS: Encontre a linha digitável completa.
    
    Retorne APENAS JSON:
    {{ "valor": 123.45, "codigo": "00000..." }}
    """
    
    # Tenta até 5 vezes (aumentei para garantir em processos longos)
    for tentativa in range(5):
        try:
            # Configura timeout de 120s para CADA chamada específica
            response = model.generate_content(
                [prompt, imagem_pil],
                request_options=RequestOptions(timeout=120) 
            )
            
            texto_resposta = response.text.replace('```json', '').replace('```', '').strip()
            
            try:
                return json.loads(texto_resposta)
            except json.JSONDecodeError:
                # Se falhar o JSON, tenta mais uma vez sem esperar muito
                logger.warning(f"JSON Inválido na tentativa {tentativa+1}")
                continue 

        except Exception as e:
            msg_erro = str(e)
            # Se for erro de Limite (429), espera exponencialmente (4s, 8s, 16s...)
            if "429" in msg_erro:
                tempo_espera = 4 * (tentativa + 1)
                logger.warning(f"Rate Limit (429). Esperando {tempo_espera}s...")
                time.sleep(tempo_espera)
            else:
                logger.error(f"Erro Gemini tentativa {tentativa+1}: {e}")
                time.sleep(2) # Espera padrão para outros erros

    return {}

def extrair_dados_pdf_fitz(pdf_bytes, tipo_doc, nome_arquivo=""):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        # Zoom de 2x é suficiente e mais rápido que resoluções gigantes
        matriz_zoom = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=matriz_zoom)
        
        img_data = pix.tobytes("jpeg")
        imagem_pil = Image.open(io.BytesIO(img_data))
        
        dados_ia = chamar_gemini_imagem(imagem_pil, tipo_doc)
        
        resultado = {
            'codigo': limpar_numeros(dados_ia.get('codigo')),
            'valor': normalizar_valor(dados_ia.get('valor')),
            'origem': 'IA_GEMINI'
        }
        
        if resultado['valor'] == 0 and nome_arquivo:
            valor_nome = extrair_valor_nome(nome_arquivo)
            if valor_nome > 0:
                resultado['valor'] = valor_nome
                resultado['origem'] = 'NOME_ARQUIVO'
        
        return resultado

    except Exception as e:
        logger.error(f"Erro fatal no PDF {nome_arquivo}: {e}")
        return {'codigo': '', 'valor': extrair_valor_nome(nome_arquivo), 'origem': 'ERRO_FATAL'}

# ============================================================
# FLUXO PRINCIPAL (COM PING PARA NÃO CAIR A CONEXÃO)
# ============================================================

def processar_reconciliacao(caminho_comprovantes, lista_caminhos_boletos, user):
    
    def emit(tipo, dados):
        return json.dumps({'type': tipo, 'data': dados}) + "\n"
    
    yield emit('log', '🚀 Iniciando processamento estendido (Timeout Alto)...')

    # --- ETAPA 1: LER COMPROVANTES ---
    yield emit('log', '📸 Lendo PDF de Comprovantes...')
    pool_comprovantes = []
    
    try:
        doc_comprovantes = fitz.open(caminho_comprovantes)
        total_paginas = len(doc_comprovantes)
        reader_zip = PdfReader(caminho_comprovantes)
        
        for i in range(total_paginas):
            # Envia um "ping" a cada iteração para o navegador saber que não travou
            yield emit('ping', {'progress': f'{i}/{total_paginas}'})
            
            page = doc_comprovantes[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_pil = Image.open(io.BytesIO(pix.tobytes("jpeg")))
            
            # REMOVI O SLEEP FIXO PREVENTIVO (isso economiza tempo). 
            # O 'chamar_gemini_imagem' já gerencia o sleep se der erro 429.
            dados_ia = chamar_gemini_imagem(img_pil, "comprovante bancário")
            
            valor = normalizar_valor(dados_ia.get('valor'))
            codigo = limpar_numeros(dados_ia.get('codigo'))
            
            writer = PdfWriter()
            writer.add_page(reader_zip.pages[i])
            bio = io.BytesIO()
            writer.write(bio)
            
            pool_comprovantes.append({
                'id': i,
                'codigo': codigo,
                'valor': valor,
                'pdf_bytes': bio.getvalue(),
                'usado': False
            })
            
            codigo_curto = f"...{codigo[-6:]}" if codigo else "N/A"
            yield emit('log', f"   🧾 Pág {i+1}: R${valor} | Cód: {codigo_curto}")
            yield emit('comp_status', {'index': i, 'msg': f"R$ {valor}"})

    except Exception as e:
        yield emit('log', f"❌ Erro leitura comprovantes: {e}")
        return

    # --- ETAPA 2: LER BOLETOS ---
    yield emit('log', '⚡ Analisando Boletos...')
    lista_final_boletos = []

    for index, path_boleto in enumerate(lista_caminhos_boletos):
        # Ping para manter conexão viva
        yield emit('ping', {'boleto': index})
        
        nome_arquivo = os.path.basename(path_boleto)
        yield emit('file_start', {'filename': nome_arquivo})
        
        try:
            with open(path_boleto, 'rb') as f:
                pdf_bytes_boleto = f.read()
            
            # Sem sleep fixo aqui também. Deixa a função da IA controlar.
            dados_boleto = extrair_dados_pdf_fitz(pdf_bytes_boleto, "boleto bancário", nome_arquivo)
            
            boleto_atual = {
                'nome': nome_arquivo,
                'codigo': dados_boleto['codigo'],
                'valor': dados_boleto['valor'],
                'pdf_bytes': pdf_bytes_boleto,
                'match': None, 
                'motivo': 'Sem comprovante compatível'
            }
            
            # --- LÓGICA DE MATCH ---
            melhor_candidato = None
            maior_score_similaridade = 0.0
            
            if boleto_atual['valor'] > 0:
                candidatos = [c for c in pool_comprovantes if not c['usado'] and abs(c['valor'] - boleto_atual['valor']) < 0.05]
                
                if candidatos:
                    for candidato in candidatos:
                        score = calcular_similaridade(boleto_atual['codigo'], candidato['codigo'])
                        if score > maior_score_similaridade:
                            maior_score_similaridade = score
                            melhor_candidato = candidato
                    
                    aceito = False
                    if maior_score_similaridade > 0.6:
                        aceito = True
                        boleto_atual['motivo'] = f"CÓDIGO ({int(maior_score_similaridade*100)}%)"
                    elif boleto_atual['codigo'] == "" and len(candidatos) > 0:
                        melhor_candidato = candidatos[0]
                        aceito = True
                        boleto_atual['motivo'] = "VALOR (Boleto s/ Cód)"
                    elif len(candidatos) == 1:
                        melhor_candidato = candidatos[0]
                        aceito = True
                        boleto_atual['motivo'] = "VALOR (Candidato Único)"
                    elif len(candidatos) > 1 and maior_score_similaridade <= 0.6:
                        melhor_candidato = candidatos[0] 
                        aceito = True
                        boleto_atual['motivo'] = "VALOR (Fila Sequencial)"

                    if aceito and melhor_candidato:
                        boleto_atual['match'] = melhor_candidato
                        melhor_candidato['usado'] = True 
            
            if boleto_atual['match']:
                yield emit('log', f"   ✅ {nome_arquivo} -> Combinado ({boleto_atual['motivo']})")
                yield emit('file_done', {'filename': nome_arquivo, 'status': 'success'})
            else:
                yield emit('log', f"   ⚠️ {nome_arquivo} -> Não encontrado")
                yield emit('file_done', {'filename': nome_arquivo, 'status': 'warning'})
                
            lista_final_boletos.append(boleto_atual)

        except Exception as e:
            yield emit('log', f"❌ Erro {nome_arquivo}: {e}")

    # --- ETAPA 3: GERAR ZIP ---
    yield emit('log', '💾 Gerando ZIP final...')
    
    try:
        output_zip = io.BytesIO()
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for boleto in lista_final_boletos:
                writer = PdfWriter()
                writer.append(io.BytesIO(boleto['pdf_bytes']))
                if boleto['match']:
                    writer.append(io.BytesIO(boleto['match']['pdf_bytes']))
                
                pdf_combinado_bytes = io.BytesIO()
                writer.write(pdf_combinado_bytes)
                zip_file.writestr(boleto['nome'], pdf_combinado_bytes.getvalue())

        pasta_destino = os.path.join(settings.MEDIA_ROOT, 'downloads')
        os.makedirs(pasta_destino, exist_ok=True)
        nome_zip = f"Conciliacao_Final_{uuid.uuid4().hex[:8]}.zip"
        caminho_completo_zip = os.path.join(pasta_destino, nome_zip)
        
        with open(caminho_completo_zip, 'wb') as f:
            f.write(output_zip.getvalue())
            
        url_download = f"{settings.MEDIA_URL}downloads/{nome_zip}"
        yield emit('finish', {'url': url_download, 'total': len(lista_final_boletos)})
        
    except Exception as e:
        yield emit('log', f"❌ Erro ao salvar ZIP: {e}")