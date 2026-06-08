import streamlit as st
import pandas as pd
from datetime import date
from datetime import datetime
from db import get_session, engine
from models import Condomino, Movimento, VotoSondagem, Sondagem, Anuncio, Assembleia, Ocorrencia, Fornecedor, Documento, Orcamento, Quota, Utilizador
from utils import configurar_sidebar, config, guardar_configs, gerar_snapshot_json, restaurar_snapshot_json
from utils import gerar_backup_unificado_zip

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
            
session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.header(":material/settings: Configurações e Segurança")

if not st.session_state.modo_leitura:
    tab_geral, tab_avisos, tab_seguranca = st.tabs([":material/business: Dados Gerais", ":material/campaign: Quadro de Avisos", ":material/security: Backup de Dados & Reset BD"])
    
    with tab_geral:
        with st.container(border=True):
            with st.form("form_config"):
                st.subheader("Configurações do Condomínio")
                nome = st.text_input("Nome do Condomínio", value=config.get("NOME_CONDOMINIO", ""), key=f"cfg_n_{st.session_state.get('form_key', 0)}")
                morada = st.text_input("Morada", value=config.get("MORADA_CONDOMINIO", ""), key=f"cfg_m_{st.session_state.get('form_key', 0)}")
                nif = st.text_input("NIF", value=config.get("NIF_CONDOMINIO", ""), key=f"cfg_nif_{st.session_state.get('form_key', 0)}")
                iban = st.text_input("IBAN para Pagamentos", value=config.get("IBAN_CONDOMINIO", ""), key=f"cfg_ib_{st.session_state.get('form_key', 0)}")
                valor_quota = st.number_input("Valor Padrão da Quota (€)", value=config.get("VALOR_MENSAL_FIXO", 50.0), min_value=0.0, key=f"cfg_v_{st.session_state.get('form_key', 0)}")
                
                if st.form_submit_button("Guardar Configurações"):
                    config["NOME_CONDOMINIO"] = nome
                    config["MORADA_CONDOMINIO"] = morada
                    config["NIF_CONDOMINIO"] = nif
                    config["IBAN_CONDOMINIO"] = iban
                    config["VALOR_MENSAL_FIXO"] = valor_quota
                    guardar_configs(config)
                    st.session_state.toast = ("Configurações atualizadas!", "✅")
                    st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()
                    
    with tab_avisos:
        with st.container(border=True):
            with st.form("form_avisos"):
                st.subheader("Avisos à Comunidade")
                aviso_ativo = st.checkbox("Mostrar aviso publicamente", value=config.get("AVISO_ATIVO", False), key=f"cfg_av_at_{st.session_state.get('form_key', 0)}")
                aviso_texto = st.text_area("Texto do Aviso", value=config.get("AVISO_GLOBAL", ""), key=f"cfg_av_txt_{st.session_state.get('form_key', 0)}")
                
                if st.form_submit_button("Atualizar Quadro de Avisos"):
                    config["AVISO_ATIVO"] = aviso_ativo
                    config["AVISO_GLOBAL"] = aviso_texto
                    guardar_configs(config)
                    st.session_state.toast = ("Aviso atualizado com sucesso!", "✅")
                    st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()
                    
    with tab_seguranca:
        with st.container(border=True):
            st.subheader("📦 Segurança Completa da Base de Dados")
            st.write("Processo de Exportação e Importação da Base de Dados num único ficheiro.")
            
            c_snap1, c_snap2 = st.columns(2)
            with c_snap1:
                st.write("**1. Backup da Segurança:**")
                try:
                    dados_json_dump = gerar_snapshot_json()
                    st.download_button(
                        "📥 Exportar Segurança Completa (.json)",
                        data=dados_json_dump,
                        file_name=f"DUMP_CONDOMINIO_{date.today()}.json",
                        mime="application/json",
                        use_container_width=True,
                        type="secondary"
                    )
                except Exception as e_snap:
                    st.error(f"Erro ao comprimir dados: {e_snap}")
                    
            with c_snap2:
                st.write("**2. Restore da Segurança:**")
                arq_import_json = st.file_uploader("Importar Ficheiro .json", type=["json"], key="upload_snapshot_json")
                if arq_import_json is not None:
                    if st.button("🔄 Executar Restauro da Segurança Agora", use_container_width=True, type="primary"):
                        conteudo_json_string = arq_import_json.read().decode("utf-8")
                        sucesso, msg_res = restaurar_snapshot_json(conteudo_json_string)
                        if sucesso:
                            st.success(msg_res)
                            import time
                            time.sleep(2)
                            st.session_state.logado = False
                            st.session_state.username = None
                            st.rerun()
                        else:
                            st.error(msg_res)

        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("📊 Exportações Parciais (Excel)")
            col_b1, col_b2 = st.columns(2)
            
            df_backup_cond = pd.DataFrame([{"ID": c.id, "Fração": c.fracao, "Nome": c.nome, "NIF": c.nif, "Email": c.email} for c in session.query(Condomino).all()])
            if not df_backup_cond.empty:
                csv_cond = df_backup_cond.to_csv(index=False, sep=";").encode("utf-8-sig")
                col_b1.download_button("📥 Descarregar Tabela de Condónimos (CSV)", data=csv_cond, file_name=f"Lista_Moradores_{date.today()}.csv", mime="text/csv", use_container_width=True)
            else: col_b1.info("Sem dados de moradores.")
                
            df_backup_fin = pd.DataFrame([{"Data": m.data, "Tipo": m.tipo, "Descrição": m.descricao, "Valor": m.valor} for m in session.query(Movimento).all()])
            if not df_backup_fin.empty:
                csv_fin = df_backup_fin.to_csv(index=False, sep=";").encode("utf-8-sig")
                col_b2.download_button("📥 Descarregar Finanças e Extratos (CSV)", data=csv_fin, file_name=f"Movimentos_Contas_{date.today()}.csv", mime="text/csv", use_container_width=True)
            else: col_b2.info("Sem dados financeiros.")
        
        if st.session_state.perfil == "Admin":
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.subheader("🚨 Zona de Perigo 🚨")
                st.warning("Atenção: Esta operação apaga permanentemente todos os registos. A estrutura de colunas mantém-se pronta para uso ou para receber uma importação.")
                confirmar_reset = st.checkbox("Eu compreendo os riscos e quero apagar a base de dados.")
                
                if confirmar_reset:
                    if st.button("🔥 EXECUTAR RESET AGORA", type="primary"):
                        with st.spinner("A limpar dados (Método Suave)..."):
                            try:   
                                import time
                                from sqlalchemy import text
                                
                                session.rollback()
                                session.query(VotoSondagem).delete()
                                session.query(Sondagem).delete()
                                session.query(Anuncio).delete()
                                session.query(Assembleia).delete()
                                session.query(Ocorrencia).delete()
                                session.query(Fornecedor).delete()
                                session.query(Documento).delete()
                                session.query(Movimento).delete()
                                session.query(Orcamento).delete()
                                session.query(Quota).delete()
                                session.query(Utilizador).delete()
                                session.query(Condomino).delete()
                                session.commit()
                                
                                if engine.name == "postgresql":
                                    tabelas = ["votos_sondagem", "sondagens", "anuncios", "assembleias", "ocorrencias", "fornecedores", "documentos", "movimentos", "orcamentos", "quotas", "utilizadores", "condominos"]
                                    for tabela in tabelas:
                                        try: session.execute(text(f"ALTER SEQUENCE {tabela}_id_seq RESTART WITH 1;"))
                                        except Exception: session.rollback()
                                    session.commit()
                                
                                st.success("✔️ Limpeza da Base de Dados concluída")
                                time.sleep(1.5)
                                st.session_state.logado = False
                                st.session_state.username = None
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Erro ao tentar limpar: {e}")
