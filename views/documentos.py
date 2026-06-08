import streamlit as st
import pandas as pd
import os

from db import get_session
from models import Documento
from utils import configurar_sidebar

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.header(":material/folder_open: Arquivo Digital de Documentos")

if not st.session_state.modo_leitura:
    with st.expander(":material/note_add: Arquivar Novo Documento", expanded=False):
        with st.form("form_upload"):
            st.text_input("Carregado por", value=st.session_state.username, disabled=True)
            categoria = st.selectbox("Categoria", ["Atas de Assembleia", "Apólices de Seguro", "Faturas e Recibos", "Contratos", "Manuais", "Outros"], key=f"d_cat_{st.session_state.get('form_key', 0)}")
            ficheiro = st.file_uploader("Selecione o ficheiro", type=["pdf", "jpg", "png", "jpeg"], key=f"d_f_{st.session_state.get('form_key', 0)}")
            
            if st.form_submit_button("Guardar Documento") and ficheiro is not None:
                if not os.path.exists("uploads"): os.makedirs("uploads")
                caminho = os.path.join("uploads", ficheiro.name)
                with open(caminho, "wb") as f: f.write(ficheiro.getbuffer())
                
                session.add(Documento(nome_ficheiro=ficheiro.name, categoria=categoria, caminho=caminho, carregado_por=st.session_state.username))
                session.commit(); st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()

docs = session.query(Documento).order_by(Documento.id.desc()).all()
if docs:
    with st.container(border=True):
        df_docs = pd.DataFrame([{"ID": d.id, "Data": d.data_upload, "Categoria": d.categoria, "Nome": d.nome_ficheiro, "Utilizador": d.carregado_por if d.carregado_por else "Sistema/Antigo"} for d in docs])
        evento_doc = st.dataframe(df_docs, use_container_width=True, hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
    
    if evento_doc.selection.rows:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            doc_obj = session.get(Documento, int(df_docs.iloc[evento_doc.selection.rows[0]]["ID"]))
            col_info, col_down, col_del = st.columns([2, 1, 1])
            
            utilizador_txt = doc_obj.carregado_por if doc_obj.carregado_por else "Sistema/Antigo"
            col_info.info(f":material/push_pin: Selecionado: **{doc_obj.nome_ficheiro}** | Carregado por: **{utilizador_txt}**")
            
            if st.session_state.perm_download_docs:
                try:
                    with open(doc_obj.caminho, "rb") as file: col_down.download_button("📥 Baixar", data=file, file_name=doc_obj.nome_ficheiro, use_container_width=True)
                except FileNotFoundError: col_down.error("Ficheiro físico não encontrado.")
            else: col_down.warning("🚫 Sem permissão de download")
                
            if not st.session_state.modo_leitura:
                pode_apagar = (st.session_state.perfil == "Admin") or (doc_obj.carregado_por == st.session_state.username)
                if pode_apagar:
                    if col_del.button("🗑️ Apagar", use_container_width=True):
                        if os.path.exists(doc_obj.caminho): os.remove(doc_obj.caminho) 
                        session.delete(doc_obj); session.commit(); st.rerun()
else: st.info("O arquivo está vazio.")