import streamlit as st
from db import get_session
from utils import gerar_backup_unificado_zip 
from datetime import datetime

# Inicializa a sessão da Base de Dados
session = get_session()

st.title("⚙️ Configurações do Sistema")
st.markdown("Gerencie os parâmetros globais, utilizadores e cópias de segurança do portal.")

# Criação de separadores organizados para a tua view
tab_geral, tab_utilizadores, tab_seguranca = st.tabs([
    "ℹ️ Geral", 
    "👥 Gestão de Acessos", 
    "🔒 Cópia de Segurança (Backup)"
])

# --- SEPARADOR 1: GERAL ---
with tab_geral:
    st.subheader("Informações do Portal")
    st.write("A aplicação está a correr com sucesso na infraestrutura privada (VPS).")
    with st.container(border=True):
        st.markdown("**Versão do Sistema:** 2.0 (Arquitetura Modular)")
        st.markdown("**Armazenamento Local:** Ativo (Pasta `/uploads` persistente)")
        st.markdown("**Ligação Cloud Banco de Dados:** Ativa (Supabase PostgreSQL)")

# --- SEPARADOR 2: GESTÃO DE ACESSOS (Espaço reservado para a tua lógica antiga) ---
with tab_utilizadores:
    st.subheader("Controlo de Utilizadores")
    st.caption("A gestão avançada e permissões de utilizadores podem ser editadas através do menu 'Gestão de Acessos' no painel lateral.")

# --- SEPARADOR 3: CÓPIA DE SEGURANÇA (A Nova Inovação) ---
with tab_seguranca:
    st.subheader("Salvaguarda Total do Condomínio")
    st.info(
        "💡 **Como funciona o Backup Unificado?** Ao clicar no botão abaixo, o sistema liga-se "
        "ao Supabase para extrair os registos de texto e, em simultâneo, recolhe todos os ficheiros "
        "físicos (PDFs de faturas, atas, comprovativos) armazenados no disco da VPS. "
        "Tudo é compactado num único ficheiro `.zip` descarregável."
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Contentor visual do bloco de Backup
    with st.container(border=True):
        col_icone, col_texto = st.columns([0.5, 3.5])
        with col_icone:
            st.markdown("<h1 style='text-align: center; margin: 0; padding-top: 5px;'>📦</h1>", unsafe_allow_html=True)
        with col_texto:
            st.markdown("### Criar Cópia de Segurança Completa")
            st.caption("Ficheiro único recomendado para auditorias anuais ou migrações de servidor.")
        
        # Nome dinâmico para o ficheiro zip baseado na data atual
        data_atual = datetime.now().strftime("%Y-%m-%d")
        nome_ficheiro_zip = f"backup_total_condominio_{data_atual}.zip"
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        try:
            # O processamento do ZIP só é executado no momento exato do clique
            st.download_button(
                label="⚡ Descarregar Backup Unificado (.zip)",
                data=gerar_backup_unificado_zip(session),
                file_name=nome_ficheiro_zip,
                mime="application/zip",
                type="primary",
                use_container_width=True
            )
            st.success("✅ Ficheiro ZIP estruturado em tempo real. Pronto para transferência.")
        except Exception as e:
            st.error(f"❌ Erro ao compilar o backup unificado: {str(e)}")
