import streamlit as st
import pandas as pd
import os
import time
from sqlalchemy import and_

from db import get_session
from models import Ocorrencia
from utils import configurar_sidebar, hoje

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.header(":material/build: Gestão de Ocorrências")

if not st.session_state.modo_leitura:
    with st.expander(":material/add_alert: Registar Nova Ocorrência"):
        with st.form("f_oc"):
            st.text_input("Reportado por", value=st.session_state.username, disabled=True)
            tit = st.text_input("Assunto (ex: Fuga de água) *", key=f"o_tit_{st.session_state.get('form_key', 0)}")
            desc = st.text_area("Descrição detalhada do problem *", key=f"o_desc_{st.session_state.get('form_key', 0)}")
            
            st.write("**Provas Fotográficas (Opcional)**")
            c1, c2 = st.columns(2)
            with c1: foto1 = st.file_uploader("Fotografia 1", type=["jpg", "jpeg", "png"], key=f"o_f1_{st.session_state.get('form_key', 0)}")
            with c2: foto2 = st.file_uploader("Fotografia 2", type=["jpg", "jpeg", "png"], key=f"o_f2_{st.session_state.get('form_key', 0)}")
            
            if st.form_submit_button("Reportar Ocorrência"):
                if not tit.strip() or not desc.strip(): st.error("⚠️ O preenchimento do Assunto e da Descrição é obrigatório!")
                else:
                    if not os.path.exists("uploads"): os.makedirs("uploads")
                    caminho_f1, caminho_f2 = None, None
                    timestamp_str = str(int(time.time()))
                    
                    if foto1:
                        caminho_f1 = os.path.join("uploads", f"oc_{timestamp_str}_1_{foto1.name}")
                        with open(caminho_f1, "wb") as f: f.write(foto1.getbuffer())
                    if foto2:
                        caminho_f2 = os.path.join("uploads", f"oc_{timestamp_str}_2_{foto2.name}")
                        with open(caminho_f2, "wb") as f: f.write(foto2.getbuffer())

                    session.add(Ocorrencia(
                        titulo=tit, 
                        descricao=desc, 
                        data_criacao=hoje.strftime("%Y-%m-%d"), 
                        criado_por=st.session_state.username, 
                        foto1=caminho_f1, 
                        foto2=caminho_f2
                    ))
                    session.commit()
                    st.session_state.toast = ("Ocorrência registada com sucesso!", "✅")
                    st.session_state.form_key = st.session_state.get('form_key', 0) + 1
                    st.rerun()

ocs = session.query(Ocorrencia).filter(and_(Ocorrencia.data_criacao >= str_inicio, Ocorrencia.data_criacao < str_fim)).all()
if ocs:
    with st.container(border=True):
        df_ocs = pd.DataFrame([{"ID": o.id, "Data": o.data_criacao, "Utilizador": o.criado_por if o.criado_por else "N/D", "Estado": "✅ Resolvido" if o.resolvida else "🔴 Pendente", "Assunto": o.titulo} for o in ocs])
        evento_oc = st.dataframe(df_ocs, use_container_width=True, hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
    
    if evento_oc.selection.rows:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            oc_obj = session.get(Ocorrencia, int(df_ocs.iloc[evento_oc.selection.rows[0]]["ID"]))
            col_info, col_estado, col_del = st.columns([2, 1, 1])
            
            col_info.info(f":material/push_pin: Submetido por: **{oc_obj.criado_por}** | Assunto: **{oc_obj.titulo}**")
            col_info.write(f"**Descrição:** {oc_obj.descricao if oc_obj.descricao else 'Sem descrição'}")
            
            if oc_obj.foto1 or oc_obj.foto2:
                st.write("**Fotografias Anexadas:**")
                c_img1, c_img2 = st.columns(2)
                if oc_obj.foto1 and os.path.exists(oc_obj.foto1): c_img1.image(oc_obj.foto1, use_container_width=True)
                if oc_obj.foto2 and os.path.exists(oc_obj.foto2): c_img2.image(oc_obj.foto2, use_container_width=True)

            if not st.session_state.modo_leitura and st.session_state.perfil == "Admin":
                if col_estado.button(":material/lock_open: Reabrir" if oc_obj.resolvida else ":material/check_circle: Resolver", use_container_width=True):
                    oc_obj.resolvida = not oc_obj.resolvida; session.commit(); st.rerun()
                if col_del.button(":material/delete: Apagar", use_container_width=True):
                    session.delete(oc_obj); session.commit(); st.session_state.toast = ("Ocorrência apagada!", "🗑️"); st.rerun()
else: 
    st.info("Nenhuma ocorrência neste período.")