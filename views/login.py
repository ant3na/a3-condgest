import streamlit as st
import os
from db import get_session
from models import Utilizador

# Verificação da biblioteca de passwords
try:
    from werkzeug.security import generate_password_hash, check_password_hash
    WERKZEUG_INSTALLED = True
except ImportError:
    WERKZEUG_INSTALLED = False

session = get_session()

def pagina_login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.2, 1.2, 1.2]) 
    
    with c2:
        if not WERKZEUG_INSTALLED:
            st.error("⚠️ Erro Crítico: A biblioteca 'werkzeug' não está instalada.")
            return
            
        with st.container(border=True):
            if os.path.exists("logo.png"):
                col_esp, col_img, col_esp2 = st.columns([1, 1.5, 1])
                with col_img: st.image("logo.png", use_container_width=True)
            
            st.markdown("""
            <div style='text-align: center;'>
                <h2 style='margin-bottom: 0px; color: #1e293b;'>A3® Portal do Condomínio</h2>
                <p style='color: #64748b; font-size: 14px; margin-top: 5px; margin-bottom: 20px;'>Portal de Administração e Moradores</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("form_login", clear_on_submit=True):
                user = st.text_input("👤 Nome de Utilizador", placeholder="Insira o seu utilizador")
                pwd = st.text_input("🔒 Password", type="password", placeholder="Insira a sua password")
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)
                
                if submit:
                    if not user or not pwd:
                        st.warning("⚠️ Preencha os dois campos para entrar.")
                    else:
                        utilizador_db = session.query(Utilizador).filter_by(username=user.lower()).first()
                        if utilizador_db and check_password_hash(utilizador_db.password_hash, pwd):
                            # Guardar os estados na sessão
                            st.session_state.logado = True
                            st.session_state.user_id = utilizador_db.id
                            st.session_state.username = utilizador_db.username
                            st.session_state.perfil = utilizador_db.perfil
                            st.session_state.condomino_id = utilizador_db.condomino_id
                            
                            st.session_state.perm_dashboard = utilizador_db.perm_dashboard
                            st.session_state.perm_condominos = utilizador_db.perm_condominos
                            st.session_state.perm_quotas = utilizador_db.perm_quotas
                            st.session_state.perm_financas = utilizador_db.perm_financas
                            st.session_state.perm_recibos = utilizador_db.perm_recibos
                            st.session_state.perm_assembleias = utilizador_db.perm_assembleias
                            st.session_state.perm_arquivo = utilizador_db.perm_arquivo
                            st.session_state.perm_fornecedores = utilizador_db.perm_fornecedores
                            st.session_state.perm_ocorrencias = utilizador_db.perm_ocorrencias
                            st.session_state.perm_mural = utilizador_db.perm_mural
                            
                            st.session_state.modo_leitura = utilizador_db.modo_leitura
                            st.session_state.perm_download_docs = utilizador_db.perm_download_docs
                            st.rerun()
                        else: 
                            st.error("❌ Credenciais incorretas. Tente novamente.")
                            
            st.markdown("""
            <div style='text-align: center; margin-top: 15px;'>
                <p style='color: #94a3b8; font-size: 11px;'>© 2026 A3 Technologies | Versão 2.0</p>
            </div>
            """, unsafe_allow_html=True)