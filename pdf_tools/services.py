import io
import os # <--- Necessário para ler arquivos do disco e pegar o nome base
import zipfile
import time
from pypdf import PdfReader, PdfWriter
import google.generativeai as genai
import json
from django.conf import settings

# Configura a chave
genai.configure(api_key=settings.GOOGLE_API_KEY)

def extract_text_from_pdf(pdf_path):
    # Agora abrimos o arquivo usando o caminho do disco
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def analisar_com_gemini(texto, tipo_doc):
    """
    Usa o modelo FLASH (mais rápido) com sistema de Retry para erro 429.
    """
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    Analise o texto abaixo extraído de um {tipo_doc}.
    Retorne APENAS um objeto JSON (sem markdown) com os campos:
    - "valor": (float, use ponto para decimais, ex: 150.50)
    - "identificador": (string, codigo de barras ou nome. Algo único).
    
    Texto:
    {texto[:4000]}
    """
    
    for tentativa in range(1, 4):
        try:
            response = model.generate_content(prompt)
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_text)
        except Exception as e:
            print(f"Tentativa {tentativa} falhou: {e}")
            if "429" in str(e):
                print("Limite atingido. Esperando 10 segundos...")
                time.sleep(10)
            else:
                break # Outro erro, para de tentar

    return {"valor": 0.0, "identificador": ""}

def processar_conciliacao(lista_caminhos_boletos, caminho_comprovantes):
    # 1. INICIA O CONTADOR DE PÁGINAS
    total_paginas_contadas = 0

    # A. Ler Comprovantes (Do disco)
    comprovantes_map = []
    reader_comp = PdfReader(caminho_comprovantes)
    
    # SOMA AS PÁGINAS DO ARQUIVO DE COMPROVANTES
    total_paginas_contadas += len(reader_comp.pages)
    
    print(f"Processando {len(reader_comp.pages)} comprovantes...")
    
    for i, page in enumerate(reader_comp.pages):
        texto_pg = page.extract_text()
        
        dados = analisar_com_gemini(texto_pg, "comprovante")
        print(f"Comprovante {i+1}: {dados}")
        
        time.sleep(4) # Delay de segurança
        
        writer_temp = PdfWriter()
        writer_temp.add_page(page)
        pdf_bytes = io.BytesIO()
        writer_temp.write(pdf_bytes)
        pdf_bytes.seek(0)
        
        comprovantes_map.append({
            'page_obj': pdf_bytes,
            'dados': dados,
            'usado': False
        })

    # B. Ler Boletos (Do disco)
    output_zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(output_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        for boleto_path in lista_caminhos_boletos:
            # Conta páginas deste boleto lendo do disco
            temp_reader = PdfReader(boleto_path)
            total_paginas_contadas += len(temp_reader.pages)
            
            # Extrai texto
            texto_boleto = extract_text_from_pdf(boleto_path)
            dados_boleto = analisar_com_gemini(texto_boleto, "boleto")
            
            print(f"Boleto processado: {dados_boleto}")
            time.sleep(4) # Delay de segurança
            
            # Lógica de Matching
            comprovante_match = None
            for comp in comprovantes_map:
                if not comp['usado']:
                    val_bol = float(dados_boleto.get('valor') or 0)
                    val_comp = float(comp['dados'].get('valor') or 0)
                    
                    if val_bol > 0 and abs(val_bol - val_comp) < 0.05:
                        comprovante_match = comp
                        comp['usado'] = True
                        break
            
            # Cria o PDF Final
            writer_final = PdfWriter()
            
            # Adiciona Boleto (Lendo do disco)
            reader_bol = PdfReader(boleto_path)
            for p in reader_bol.pages:
                writer_final.add_page(p)
            
            # Adiciona Comprovante (se achou)
            if comprovante_match:
                reader_match = PdfReader(comprovante_match['page_obj'])
                writer_final.add_page(reader_match.pages[0])
            
            # PEGA O NOME DO ARQUIVO LIMPO (sem o caminho da pasta temp)
            nome_arquivo = os.path.basename(boleto_path)
            
            # Salva no ZIP
            pdf_output = io.BytesIO()
            writer_final.write(pdf_output)
            zip_file.writestr(nome_arquivo, pdf_output.getvalue())

    output_zip_buffer.seek(0)
    
    # RETORNA O ARQUIVO E O TOTAL DE PÁGINAS
    return output_zip_buffer, total_paginas_contadas