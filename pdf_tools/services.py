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
from django.conf import settings

# Configuração do logger para registrar informações e erros.
logger = logging.getLogger(__name__)

# Configura a API do Google Gemini com a chave das configurações do Django.
genai.configure(api_key=settings.GOOGLE_API_KEY)

# ============================================================
# FERRAMENTAS AUXILIARES
# ============================================================

def limpar_numeros(texto):
    """Remove todos os caracteres não numéricos de uma string."""
    return re.sub(r'\D', '', str(texto or ""))

def calcular_similaridade(a, b):
    """Calcula a similaridade entre duas strings (útil para códigos de barras)."""
    if not a or not b: return 0.0
    return SequenceMatcher(None, a, b).ratio()

def normalizar_valor(v_str):
    """Converte uma string de valor monetário (ex: 'R$ 1.234,56') para float (1234.56)."""
    try:
        if isinstance(v_str, (float, int)): return float(v_str)
        v = str(v_str).replace('R$', '').strip()
        # Trata o padrão brasileiro (milhar com '.' e decimal com ',')
        if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
        # Trata o padrão com apenas a vírgula como decimal
        elif ',' in v: v = v.replace(',', '.')
        return float(v)
    except (ValueError, TypeError):
        return 0.0

def extrair_valor_nome(nome_arquivo):
    """Tenta extrair um valor monetário do nome do arquivo como um fallback."""
    # Procura por padrões como R$123_45, R$123-45, R$123,45 no nome
    match = re.search(r'R\$\s?(\d+)[_.,-](\d{2})', nome_arquivo)
    if match:
        try:
            return float(f"{match.group(1)}.{match.group(2)}")
        except:
            pass
    return 0.0

# ============================================================
# FUNÇÃO DA IA GEMINI (ATUALIZADA)
# ============================================================

def chamar_gemini_imagem(imagem_pil, tipo_doc):
    """
    Envia uma imagem para a IA Gemini 1.5 Flash e extrai os dados.
    Inclui lógica de retry para lidar com limites de requisições da API.
    """
    # Usando o modelo Flash mais recente e estável.
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    # Prompt refinado para maior precisão e robustez.
    prompt = f"""
    Analise esta imagem de um {tipo_doc}.
    O documento pode estar rotacionado, amassado ou com baixa qualidade.
    
    TAREFA:
    1.  **VALOR TOTAL:** Encontre o valor total do documento.
    2.  **CÓDIGO DE BARRAS:** Encontre a linha digitável (código de barras numérico). Copie todos os números sem exceção.
    
    REGRAS:
    - Se um campo não for encontrado, retorne null para ele.
    - Retorne APENAS um objeto JSON válido.
    
    Formato de saída:
    {{
      "valor": 123.45,
      "codigo": "00190500954014481606906809358314187220000012345"
    }}
    """
    
    # Lógica de retry: tenta até 3 vezes em caso de falha.
    for tentativa in range(3):
        try:
            response = model.generate_content([prompt, imagem_pil])
            
            # Limpa a resposta para garantir que temos apenas o JSON.
            texto_resposta = response.text.replace('```json', '').replace('```', '').strip()
            
            # Tenta decodificar o JSON. Se falhar, continua para a próxima tentativa.
            try:
                return json.loads(texto_resposta)
            except json.JSONDecodeError:
                logger.warning(f"Tentativa {tentativa+1}: Gemini retornou texto inválido: {texto_resposta}")
                continue # Pula para a próxima tentativa do loop

        except Exception as e:
            # Se o erro for de "Rate Limit" (muitas requisições), espera mais.
            if "429" in str(e):
                logger.warning(f"Tentativa {tentativa+1}: Rate limit atingido. Aguardando 4s...")
                time.sleep(4)
            else:
                logger.error(f"Tentativa {tentativa+1}: Erro na chamada da Gemini: {e}")
                time.sleep(1) # Espera curta para outros tipos de erro.

    # Se todas as tentativas falharem, retorna um dicionário vazio.
    return {}

def extrair_dados_pdf_fitz(pdf_bytes, tipo_doc, nome_arquivo=""):
    """
    Usa a biblioteca Fitz (PyMuPDF) para converter a primeira página de um PDF em imagem
    de alta qualidade e depois usa a função da Gemini para extrair os dados.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]  # Pega a primeira página
        
        # Aumenta a resolução da imagem em 2x (zoom). Isso melhora MUITO a precisão da IA.
        matriz_zoom = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=matriz_zoom)
        
        img_data = pix.tobytes("jpeg")
        imagem_pil = Image.open(io.BytesIO(img_data))
        
        # Chama a função da IA para ler os dados da imagem.
        dados_ia = chamar_gemini_imagem(imagem_pil, tipo_doc)
        
        resultado = {
            'codigo': limpar_numeros(dados_ia.get('codigo')),
            'valor': normalizar_valor(dados_ia.get('valor')),
            'origem': 'IA_GEMINI'
        }
        
        # Fallback: Se a IA não encontrou o valor, tenta extrair do nome do arquivo.
        if resultado['valor'] == 0 and nome_arquivo:
            valor_nome = extrair_valor_nome(nome_arquivo)
            if valor_nome > 0:
                resultado['valor'] = valor_nome
                resultado['origem'] = 'NOME_ARQUIVO'
        
        return resultado

    except Exception as e:
        logger.error(f"Erro ao extrair dados do PDF '{nome_arquivo}': {e}")
        # Fallback final em caso de erro grave na leitura do PDF.
        valor_nome = extrair_valor_nome(nome_arquivo)
        return {'codigo': '', 'valor': valor_nome, 'origem': 'ERRO_FATAL'}

# ============================================================
# FLUXO PRINCIPAL DA RECONCILIAÇÃO
# ============================================================

def processar_reconciliacao(caminho_comprovantes, lista_caminhos_boletos, user):
    """
    Orquestra todo o processo:
    1. Lê todas as páginas do PDF de comprovantes.
    2. Lê cada arquivo de boleto.
    3. Tenta combinar cada boleto com um comprovante disponível.
    4. Gera um arquivo ZIP com os pares combinados.
    """
    
    # Função auxiliar para formatar os eventos enviados ao frontend.
    def emit(tipo, dados):
        return json.dumps({'type': tipo, 'data': dados}) + "\n"
    
    yield emit('log', '🚀 Iniciando reconciliação com Gemini 1.5 Flash...')

    # --- ETAPA 1: LER E PROCESSAR O PDF DE COMPROVANTES ---
    yield emit('log', '📸 Lendo Comprovantes (Modo Lento e Preciso)...')
    pool_comprovantes = []
    
    try:
        # Abre o PDF de comprovantes com Fitz para gerar as imagens.
        doc_comprovantes = fitz.open(caminho_comprovantes)
        total_paginas = len(doc_comprovantes)
        
        # Abre o mesmo PDF com PyPDF, que é eficiente para extrair os bytes de cada página.
        reader_zip = PdfReader(caminho_comprovantes)
        
        for i in range(total_paginas):
            page = doc_comprovantes[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_pil = Image.open(io.BytesIO(pix.tobytes("jpeg")))
            
            # A PAUSA ESTRATÉGICA: Essencial para não sobrecarregar a API da Gemini.
            time.sleep(1.5)
            dados_ia = chamar_gemini_imagem(img_pil, "comprovante bancário")
            
            valor = normalizar_valor(dados_ia.get('valor'))
            codigo = limpar_numeros(dados_ia.get('codigo'))
            
            # Prepara os bytes da página individual para o ZIP final.
            writer = PdfWriter()
            writer.add_page(reader_zip.pages[i])
            bio = io.BytesIO()
            writer.write(bio)
            
            # Adiciona o comprovante processado à nossa "piscina" de comprovantes disponíveis.
            pool_comprovantes.append({
                'id': i,
                'codigo': codigo,
                'valor': valor,
                'pdf_bytes': bio.getvalue(),
                'usado': False  # Flag para controlar se já foi combinado com um boleto.
            })
            
            codigo_curto = f"...{codigo[-6:]}" if codigo else "N/A"
            yield emit('log', f"   🧾 Comprovante Pág {i+1}: R${valor} | Cód: {codigo_curto}")
            yield emit('comp_status', {'index': i, 'msg': f"R$ {valor}"})

    except Exception as e:
        yield emit('log', f"❌ Erro crítico ao ler comprovantes: {e}")
        return

    # --- ETAPA 2: LER OS BOLETOS E TENTAR O "MATCH" ---
    yield emit('log', '⚡ Analisando Boletos e combinando com comprovantes...')
    lista_final_boletos = []

    for path_boleto in lista_caminhos_boletos:
        nome_arquivo = os.path.basename(path_boleto)
        yield emit('file_start', {'filename': nome_arquivo})
        
        try:
            with open(path_boleto, 'rb') as f:
                pdf_bytes_boleto = f.read()
            
            # Outra pausa para garantir o espaçamento entre chamadas à API.
            time.sleep(1)
            dados_boleto = extrair_dados_pdf_fitz(pdf_bytes_boleto, "boleto bancário", nome_arquivo)
            
            boleto_atual = {
                'nome': nome_arquivo,
                'codigo': dados_boleto['codigo'],
                'valor': dados_boleto['valor'],
                'pdf_bytes': pdf_bytes_boleto,
                'match': None, # Armazenará o comprovante combinado.
                'motivo': 'Sem comprovante compatível'
            }
            
            # --- LÓGICA DE COMBINAÇÃO (O CORAÇÃO DO PROCESSO) ---
            melhor_candidato = None
            maior_score_similaridade = 0.0
            
            # Só tenta combinar se o boleto tiver um valor válido.
            if boleto_atual['valor'] > 0:
                # 1. Filtra os comprovantes disponíveis que têm o mesmo valor (com uma pequena margem de erro).
                candidatos = [c for c in pool_comprovantes if not c['usado'] and abs(c['valor'] - boleto_atual['valor']) < 0.05]
                
                if candidatos:
                    # 2. Prioridade 1: Encontrar o comprovante com o código de barras mais parecido.
                    for candidato in candidatos:
                        score = calcular_similaridade(boleto_atual['codigo'], candidato['codigo'])
                        if score > maior_score_similaridade:
                            maior_score_similaridade = score
                            melhor_candidato = candidato
                    
                    # 3. Lógica de Decisão para o "Match"
                    aceito = False
                    if maior_score_similaridade > 0.6: # Se a similaridade do código for alta, é um match!
                        aceito = True
                        boleto_atual['motivo'] = f"CÓDIGO ({int(maior_score_similaridade*100)}%)"
                    elif boleto_atual['codigo'] == "" and len(candidatos) > 0: # Se o boleto está sem código, pega o primeiro da fila com mesmo valor.
                        melhor_candidato = candidatos[0] # FIFO
                        aceito = True
                        boleto_atual['motivo'] = "VALOR (Boleto s/ Cód)"
                    elif len(candidatos) == 1: # Se só sobrou um comprovante com aquele valor, é ele!
                        melhor_candidato = candidatos[0]
                        aceito = True
                        boleto_atual['motivo'] = "VALOR (Candidato Único)"
                    elif len(candidatos) > 1 and maior_score_similaridade <= 0.6: # Múltiplos candidatos e códigos não batem.
                        # Assume o primeiro da fila para não perder o match. Resolve o caso de vários boletos com valores iguais.
                        melhor_candidato = candidatos[0] # FIFO
                        aceito = True
                        boleto_atual['motivo'] = "VALOR (Fila Sequencial)"

                    if aceito and melhor_candidato:
                        boleto_atual['match'] = melhor_candidato
                        melhor_candidato['usado'] = True # Marca o comprovante como usado.
            
            # --- FIM DA LÓGICA DE COMBINAÇÃO ---
            
            if boleto_atual['match']:
                yield emit('log', f"   ✅ {nome_arquivo} -> Combinado por {boleto_atual['motivo']}")
                yield emit('file_done', {'filename': nome_arquivo, 'status': 'success'})
            else:
                yield emit('log', f"   ⚠️ {nome_arquivo} (R${boleto_atual['valor']}) -> Não encontrado")
                yield emit('file_done', {'filename': nome_arquivo, 'status': 'warning'})
                
            lista_final_boletos.append(boleto_atual)

        except Exception as e:
            yield emit('log', f"❌ Erro no arquivo {nome_arquivo}: {e}")

    # --- ETAPA 3: GERAR O ARQUIVO ZIP DE SAÍDA ---
    yield emit('log', '💾 Montando o arquivo ZIP final...')
    output_zip = io.BytesIO()
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for boleto in lista_final_boletos:
            writer = PdfWriter()
            # Adiciona o boleto original
            writer.append(io.BytesIO(boleto['pdf_bytes']))
            # Se encontrou um par, adiciona o comprovante logo em seguida
            if boleto['match']:
                writer.append(io.BytesIO(boleto['match']['pdf_bytes']))
            
            # Salva o PDF combinado (1 ou 2 páginas) em memória
            pdf_combinado_bytes = io.BytesIO()
            writer.write(pdf_combinado_bytes)
            
            # Adiciona o PDF combinado ao arquivo ZIP
            zip_file.writestr(boleto['nome'], pdf_combinado_bytes.getvalue())

    # Salva o arquivo ZIP em disco
    pasta_destino = os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(pasta_destino, exist_ok=True)
    nome_zip = f"Conciliacao_Final_{uuid.uuid4().hex[:8]}.zip"
    caminho_completo_zip = os.path.join(pasta_destino, nome_zip)
    
    with open(caminho_completo_zip, 'wb') as f:
        f.write(output_zip.getvalue())
        
    url_download = f"{settings.MEDIA_URL}downloads/{nome_zip}"
    yield emit('finish', {'url': url_download, 'total': len(lista_final_boletos)})