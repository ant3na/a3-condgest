import os
import io
import json
import zipfile
from datetime import datetime
import streamlit as st
from sqlalchemy import text

def gerar_backup_unificado_zip(session):
    """
    Gera um ficheiro ZIP em memória contendo o dump de dados do Supabase
    e todos os ficheiros físicos contidos na pasta 'uploads' da VPS.
    """
    # 1. Criar um buffer em memória para o ficheiro ZIP (evita criar lixo no disco da VPS)
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        # --- FRENTE A: DUMP DA BASE DE DADOS (SUPABASE) ---
        # Lista de tabelas do teu sistema para backup
        tabelas = [
            "utilizadores", "condominos", "quotas", "movimentos", 
            "recibos", "assembleias", "documentos", "fornecedores", 
            "ocorrencias", "mural"
        ]
        
        dados_globais = {}
        
        for tabela in tabelas:
            try:
                # Executa uma query direta para extrair os dados de cada tabela
                result = session.execute(text(f"SELECT * FROM {tabela}"))
                colunas = result.keys()
                # Transforma as linhas em dicionários
                linhas = [dict(zip(colunas, row)) for row in result.fetchall()]
                
                # Trata formatos de data/hora e bytes para que o JSON não quebre
                for linha in linhas:
                    for k, v in linha.items():
                        if hasattr(v, "isoformat"):  # Converte datetime/date para texto
                            linha[k] = v.isoformat()
                        elif isinstance(v, bytes):
                            linha[k] = v.decode('utf-8', errors='ignore')
                            
                dados_globais[tabela] = linhas
            except Exception as e:
                # Se a tabela ainda não existir no teu banco, regista o aviso no JSON em vez de falhar
                dados_globais[tabela] = f"Aviso: {str(e)}"
        
        # Escreve o dump estruturado num ficheiro JSON dentro do arquivo ZIP
        json_data = json.dumps(dados_globais, indent=4, ensure_ascii=False)
        zip_file.writestr("database_dump.json", json_data)
        
        # --- FRENTE B: COPIAR FICHEIROS FÍSICOS (PASTA UPLOADS DA VPS) ---
        pasta_uploads = "uploads"
        if os.path.exists(pasta_uploads):
            for raiz, _, ficheiros in os.walk(pasta_uploads):
                for ficheiro in ficheiros:
                    caminho_completo = os.path.join(raiz, ficheiro)
                    # Calcula o caminho relativo para a estrutura de pastas dentro do ZIP ficar limpa
                    caminho_no_zip = os.path.relpath(caminho_completo, os.path.dirname(pasta_uploads))
                    zip_file.write(caminho_completo, caminho_no_zip)
                    
    # Reposiciona o ponteiro do buffer no início para o Streamlit conseguir fazer a leitura
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
