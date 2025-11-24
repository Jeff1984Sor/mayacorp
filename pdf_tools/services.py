import io
import os
import zipfile
import time
import uuid
import json
import re
from pypdf import PdfReader, PdfWriter
from django.conf import settings

# --- FUNÇÕES DE EXTRAÇÃO PURA ---

def limpar_numeros(texto):
    """Remove tudo que não for número."""
    if not texto: return ""
    return re.sub(r'\D', '', str(texto))

def extrair_valor_nome_arquivo(nome_arquivo):
    """Tenta ler 'R$ 402_00' do nome do arquivo."""
    match = re.search(r'R\$\s?(\d+)[_.,-](\d{2})', nome_arquivo)
    if match:
        try:
            return float(f"{match.group(1)}.{match.group(2)}")
        except: pass
    return 0.0

def extrair_dados(texto, nome_arquivo=""):
    """
    Retorna dicionario com 'codigo' (string limpa) e 'valor' (float).
    """
    dados = {'codigo': '', 'valor': 0.0}
    
    # 1. Extração de Código (Busca sequencia de numeros longa)
    texto_limpo = texto.replace('\n', '').replace(' ', '').replace('.', '').replace('-', '')
    # Pega qualquer grupo de numeros com mais de 36 digitos
    match_cod = re.search(r'\d{36,}', texto_limpo)
    if match_cod:
        dados['codigo'] = match_cod.group(0) # Já está limpo pois texto_limpo tirou pontuação
        
    # 2. Extração de Valor (Texto do PDF)
    valores = re.findall(r'(?:R\$\s?)?(\d{1,3}(?:\.?\d{3})*,\d{2})', texto)
    floats = []
    for v in valores:
        try: floats.append(float(v.replace('.', '').replace(',', '.')))
        except: pass
    
    if floats:
        dados['valor'] = max(floats)
        
    # 3. Fallback: Valor do Nome do Arquivo (Se o PDF falhar)
    if dados['valor'] == 0 and nome_arquivo:
        val_nome = extrair_valor_nome_arquivo(nome_arquivo)  # ✅ CORRIGIDO: nome da função
        if val_nome > 0:
            dados['valor'] = val_nome
            
    return dados

# --- FLUXO PRINCIPAL ---

def processar_conciliacao_json_stream(lista_caminhos_boletos, caminho_comprovantes, user):
    
    def send(type, data):
        return json.dumps({'type': type, 'data': data}) + "\n"

    yield send('init_list', {'files': [os.path.basename(p) for p in lista_caminhos_boletos]})
    yield send('log', '🚀 Iniciando Análise Detalhada...')

    # --- LISTAS (TABELAS VIRTUAIS) ---
    # Cada item será: {'id': ..., 'codigo': '...', 'valor': 0.0, 'pdf': binary, 'usado': False}
    tb_comprovantes = []
    tb_boletos = []

    # ========================================================
    # ETAPA 1: MAPEAR COMPROVANTES (MOSTRAR CÓDIGOS)
    # ========================================================
    yield send('log', '📋 --- TABELA DE COMPROVANTES ---')
    
    reader_comp = PdfReader(caminho_comprovantes)
    for i, page in enumerate(reader_comp.pages):
        texto = page.extract_text() or ""
        dados = extrair_dados(texto)
        
        # Guarda binário
        writer = PdfWriter()
        writer.add_page(page)
        bio = io.BytesIO()
        writer.write(bio)
        bio.seek(0)  # ✅ CORRIGIDO: resetar ponteiro DEPOIS de escrever
        
        item = {
            'id': i,
            'origem': f"Pag {i+1}",
            'codigo': dados['codigo'],
            'valor': dados['valor'],
            'pdf_bytes': bio,
            'usado': False
        }
        tb_comprovantes.append(item)
        
        # LOG DETALHADO NA TELA
        cod_visivel = item['codigo'][:20] + "..." if item['codigo'] else "SEM_CODIGO"
        yield send('log', f"🧾 COMP {i+1}: R$ {item['valor']:.2f} | {cod_visivel}")
        yield send('comp_status', {'index': i, 'msg': f"R${item['valor']:.2f}"})

    # ========================================================
    # ETAPA 2: MAPEAR BOLETOS (MOSTRAR CÓDIGOS)
    # ========================================================
    yield send('log', '📋 --- TABELA DE BOLETOS ---')
    
    for path in lista_caminhos_boletos:
        nome_arq = os.path.basename(path)
        yield send('file_start', {'filename': nome_arq})
        
        try:
            reader = PdfReader(path)
            texto = ""
            for p in reader.pages: texto += p.extract_text() or ""
            
            dados = extrair_dados(texto, nome_arq)
            
            with open(path, 'rb') as f: 
                bio = io.BytesIO(f.read())
                bio.seek(0)  # ✅ CORRIGIDO: resetar após ler arquivo
            
            item = {
                'nome': nome_arq,
                'codigo': dados['codigo'],
                'valor': dados['valor'],
                'pdf_bytes': bio,
                'match': None,
                'metodo': ''
            }
            tb_boletos.append(item)
            
            # LOG DETALHADO NA TELA
            cod_visivel = item['codigo'][:20] + "..." if item['codigo'] else "SEM_CODIGO"
            yield send('log', f"📄 BOL ({nome_arq}): R$ {item['valor']:.2f} | {cod_visivel}")
            
            # Marca como processando visualmente
            yield send('file_done', {'filename': nome_arq, 'status': 'processing'})
            
        except Exception as e:
            yield send('log', f"❌ ERRO ao ler {nome_arq}: {str(e)}")
            yield send('file_done', {'filename': nome_arq, 'status': 'error'})
            continue

    # ========================================================
    # ETAPA 3: O CRUZAMENTO (MATCH)
    # ========================================================
    yield send('log', '⚡ --- COMPARANDO AS DUAS LISTAS ---')
    
    # 3.1 - TENTATIVA POR CÓDIGO
    for boleto in tb_boletos:
        if not boleto['codigo']: continue # Se não tem código, pula pra proxima tentativa
        
        for comp in tb_comprovantes:
            if comp['usado']: continue # Se já usou esse comp, pula
            if not comp['codigo']: continue
            
            # Compara se um contém o outro (para resolver o problema de dígitos verificadores)
            if boleto['codigo'] in comp['codigo'] or comp['codigo'] in boleto['codigo']:
                boleto['match'] = comp
                boleto['metodo'] = "CÓDIGO"
                comp['usado'] = True
                yield send('log', f"✅ MATCH CÓDIGO: {boleto['nome']} ← COMP {comp['id']+1}")
                break
                
    # 3.2 - TENTATIVA POR VALOR (FILA SEQUENCIAL)
    # Só roda para quem ainda não deu match
    for boleto in tb_boletos:
        if boleto['match']: continue # Já achou por código
        if boleto['valor'] == 0: continue # Sem valor não dá pra comparar
        
        for comp in tb_comprovantes:
            if comp['usado']: continue # Já usou
            
            if abs(boleto['valor'] - comp['valor']) < 0.05:
                boleto['match'] = comp
                boleto['metodo'] = "VALOR"
                comp['usado'] = True
                yield send('log', f"✅ MATCH VALOR: {boleto['nome']} ← COMP {comp['id']+1}")
                break

    # ========================================================
    # GERAÇÃO DO ARQUIVO FINAL
    # ========================================================
    yield send('log', '💾 Gerando Resultados...')
    
    output_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(output_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for item in tb_boletos:
            writer_final = PdfWriter()
            
            try:
                # Boleto
                item['pdf_bytes'].seek(0)  # ✅ CORRIGIDO: resetar antes de ler
                rb = PdfReader(item['pdf_bytes'])
                for p in rb.pages: writer_final.add_page(p)
                
                status = 'warning'
                if item['match']:
                    status = 'success'
                    # Comprovante
                    item['match']['pdf_bytes'].seek(0)  # ✅ CORRIGIDO: resetar antes de ler
                    rc = PdfReader(item['match']['pdf_bytes'])
                    writer_final.add_page(rc.pages[0])
                else:
                    yield send('log', f"❌ SEM PAR: {item['nome']} (Cod: {item['codigo'][:10] if item['codigo'] else 'N/A'}...)")
                
                # Atualiza ícone final na tela
                yield send('file_done', {'filename': item['nome'], 'status': status})
                
                bio = io.BytesIO()
                writer_final.write(bio)
                bio.seek(0)  # ✅ CORRIGIDO: resetar antes de salvar no ZIP
                zip_file.writestr(item['nome'], bio.getvalue())
                
            except Exception as e:
                yield send('log', f"❌ ERRO ao gerar PDF final de {item['nome']}: {str(e)}")
                yield send('file_done', {'filename': item['nome'], 'status': 'error'})
                continue

    # Finaliza
    pasta = os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(pasta, exist_ok=True)
    nome_zip = f"Debug_Conciliacao_{uuid.uuid4().hex[:8]}.zip"
    
    with open(os.path.join(pasta, nome_zip), "wb") as f:
        f.write(output_zip_buffer.getvalue())

    total = len(tb_comprovantes) + len(tb_boletos)
    if hasattr(user, 'paginas_processadas'):
        user.paginas_processadas += total
        user.save()

    yield send('finish', {'url': f"{settings.MEDIA_URL}downloads/{nome_zip}", 'total': total})