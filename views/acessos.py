import streamlit as st
import pandas as pd
from werkzeug.security import generate_password_hash
from db import get_session
from models import Condomino, Utilizador
from utils import configurar_sidebar, formatar_username, registar_atividade

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.header(":material/admin_panel_settings: Gestão de Acessos e Permissões")

tab_users, tab_perms = st.tabs([":material/person_add: Criar Utilizadores", ":material/shield: Configurar Permissões"])

with tab_users:
    conds = session.query(Condomino).all()
    if conds:
        df_acessos = pd.DataFrame([{"ID": c.id, "Fração": c.fracao, "Proprietário": c.nome, "Tem Acesso?": "✅ Sim" if session.query(Utilizador).filter_by(condomino_id=c.id).first() else "❌ Não", "Username": session.query(Utilizador).filter_by(condomino_id=c.id).first().username if session.query(Utilizador).filter_by(condomino_id=c.id).first() else "—"} for c in conds])
        with st.container(border=True):
            ev_acesso = st.dataframe(df_acessos, use_container_width=True, hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
        if ev_acesso.selection.rows:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                id_cond = int(df_acessos.iloc[ev_acesso.selection.rows[0]]["ID"])
                cond_sel = session.get(Condomino, id_cond)
                user_existente = session.query(Utilizador).filter_by(condomino_id=id_cond).first()
                st.info(f":material/push_pin: A gerir acesso de: **{cond_sel.fracao} ({cond_sel.nome})**")
                if not user_existente:
                    st.warning("Este morador ainda não tem acesso ao portal.")
                    if st.button(":material/rocket_launch: Criar Utilizador", use_container_width=True):
                        username_sugerido = formatar_username(cond_sel.nome)
                        sucesso, msg_toast = False, ""
                        
                        novo_user = Utilizador(
                            username=username_sugerido, password_hash=generate_password_hash("mudar123"), 
                            perfil="Morador", condomino_id=id_cond,
                            perm_dashboard=True, perm_condominos=False, 
                            perm_quotas=True, perm_financas=False, perm_recibos=True,
                            perm_assembleias=True, perm_arquivo=True, perm_fornecedores=False, perm_ocorrencias=True,
                            perm_mural=True,
                            modo_leitura=False, perm_download_docs=True
                        )
                        try:
                            session.add(novo_user); session.commit()
                            registar_atividade(session, st.session_state.username, "Criar Acesso", f"Utilizador {novo_user.username} criado para a fração {cond_sel.fracao}")
                            sucesso, msg_toast = True, f"Acesso criado! Login: {novo_user.username} | Pass: mudar123"
                        except Exception:
                            session.rollback()
                            novo_user_alt = Utilizador(
                                username=f"{username_sugerido}_{cond_sel.fracao.replace(' ', '').lower()}", 
                                password_hash=generate_password_hash("mudar123"), perfil="Morador", condomino_id=id_cond,
                                perm_dashboard=True, perm_condominos=False, 
                                perm_quotas=True, perm_financas=False, perm_recibos=True,
                                perm_assembleias=True, perm_arquivo=True, perm_fornecedores=False, perm_ocorrencias=True,
                                perm_mural=True,
                                modo_leitura=False, perm_download_docs=True
                            )
                            try:
                                session.add(novo_user_alt); session.commit()
                                registar_atividade(session, st.session_state.username, "Criar Acesso", f"Utilizador {novo_user.username} criado para a fração {cond_sel.fracao}")
                                sucesso, msg_toast = True, f"Acesso criado! Login: {novo_user_alt.username} | Pass: mudar123"
                            except Exception as e2: 
                                session.rollback()
                                st.error(f"Erro técnico na base de dados: {str(e2)}")
                        if sucesso: st.session_state.toast = (msg_toast, "✅"); st.rerun()
                else:
                    c1, c2 = st.columns(2)
                    if c1.button("Repor Password para 'mudar123'", use_container_width=True): 
                        user_existente.password_hash = generate_password_hash("mudar123")
                        session.commit()
                        registar_atividade(session, st.session_state.username, "Repor Password", f"Password reposta para o utilizador {user_existente.username}") # <-- INSERIR AQUI
                        st.session_state.toast = ("Reposta!", "✅")
                        st.rerun()
                        
                    if c2.button("Remover Acesso", use_container_width=True): 
                        session.delete(user_existente)
                        session.commit()
                        registar_atividade(session, st.session_state.username, "Remover Acesso", f"Acesso removido para a fração {cond_sel.fracao}") # <-- INSERIR AQUI
                        st.session_state.toast = ("Removido.", "🗑️")
                        st.rerun()
    else: st.info("Ainda não tem condóminos.")

with tab_perms:
    users = session.query(Utilizador).filter_by(perfil="Morador").all()
    if users:
        df_perms = pd.DataFrame([{"ID_User": u.id, "Fração": u.condomino.fracao if u.condomino else "N/A", "Username": u.username, "Leitura": "👁️ Ativo" if u.modo_leitura else "✏️ Não"} for u in users])
        with st.container(border=True):
            ev_perms = st.dataframe(df_perms, use_container_width=True, hide_index=True, column_config={"ID_User": None}, on_select="rerun", selection_mode="single-row")
        if ev_perms.selection.rows:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                u_sel = session.get(Utilizador, int(df_perms.iloc[ev_perms.selection.rows[0]]["ID_User"]))
                with st.form("form_perms"):
                    st.subheader(f":material/shield: Permissões Específicas de: {u_sel.username}")
                    
                    st.write("---")
                    st.write("**Restrições Globais de Ação:**")
                    val_leitura = st.checkbox(":material/visibility: Modo Leitura Global (Apenas visualiza dados)", value=u_sel.modo_leitura, key=f"p_l_{st.session_state.get('form_key', 0)}")
                    val_down = st.checkbox(":material/download: Permitir Descarregar Documentos PDF", value=u_sel.perm_download_docs, key=f"p_d_{st.session_state.get('form_key', 0)}")
                    
                    st.write("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write("**Visão Geral**")
                        val_dash = st.checkbox("Dashboard", value=u_sel.perm_dashboard, key=f"p_dash_{st.session_state.get('form_key', 0)}")
                        val_cond = st.checkbox("Condóminos", value=u_sel.perm_condominos, key=f"p_cond_{st.session_state.get('form_key', 0)}")
                    with col2:
                        st.write("**Tesouraria**")
                        val_quotas = st.checkbox("Gestão de Quotas", value=u_sel.perm_quotas, key=f"p_quotas_{st.session_state.get('form_key', 0)}")
                        val_fin = st.checkbox("Finanças & Extratos", value=u_sel.perm_financas, key=f"p_fin_{st.session_state.get('form_key', 0)}")
                        val_rec = st.checkbox("Emissão de Recibos", value=u_sel.perm_recibos, key=f"p_rec_{st.session_state.get('form_key', 0)}")
                    with col3:
                        st.write("**Operações**")
                        val_mur = st.checkbox("Mural da Comunidade", value=u_sel.perm_mural, key=f"p_mur_{st.session_state.get('form_key', 0)}")
                        val_ass = st.checkbox("Assembleias & Votações", value=u_sel.perm_assembleias, key=f"p_ass_{st.session_state.get('form_key', 0)}")
                        val_arq = st.checkbox("Arquivo Digital", value=u_sel.perm_arquivo, key=f"p_arq_{st.session_state.get('form_key', 0)}")
                        val_forn = st.checkbox("Fornecedores", value=u_sel.perm_fornecedores, key=f"p_forn_{st.session_state.get('form_key', 0)}")
                        val_oco = st.checkbox("Ocorrências", value=u_sel.perm_ocorrencias, key=f"p_oco_{st.session_state.get('form_key', 0)}")

                    if st.form_submit_button("Guardar Permissões Segmentadas", use_container_width=True):
                        u_sel.modo_leitura = val_leitura
                        u_sel.perm_download_docs = val_down
                        u_sel.perm_dashboard, u_sel.perm_condominos = val_dash, val_cond
                        u_sel.perm_quotas, u_sel.perm_financas, u_sel.perm_recibos = val_quotas, val_fin, val_rec
                        u_sel.perm_mural, u_sel.perm_assembleias = val_mur, val_ass
                        u_sel.perm_arquivo, u_sel.perm_fornecedores, u_sel.perm_ocorrencias = val_arq, val_forn, val_oco
                        session.commit()
                        registar_atividade(session, st.session_state.username, "Atualizar Permissões", f"Permissões alteradas para o utilizador {u_sel.username}")
                        st.session_state.toast = ("Permissões atualizadas com sucesso!", "✅")
                        st.session_state.form_key = st.session_state.get('form_key', 0) + 1
                        st.rerun()
    else: st.info("Sem moradores com acesso.")
