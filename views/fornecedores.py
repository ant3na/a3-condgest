import streamlit as st
import pandas as pd

from db import get_session
from models import Fornecedor
from utils import configurar_sidebar

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

def clear_edit():
    st.session_state.edit_id = None
    st.session_state.edit_type = None
    st.session_state.form_key = st.session_state.get('form_key', 0) + 1 

st.header(":material/contact_phone: Gestão de Fornecedores")

if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
    title_form = ":material/edit: Editar Fornecedor" if st.session_state.get("edit_type") == "forn" else ":material/person_add: Novo Fornecedor"
    with st.expander(title_form, expanded=(st.session_state.get("edit_type") == "forn")):
        with st.form("f_forn"):
            val_n, val_cat, val_t, val_e, val_nif, val_obs, val_resp, val_iban = "", "Geral", "", "", "", "", "", ""
            if st.session_state.get("edit_type") == "forn" and st.session_state.get("edit_id"):
                obj = session.get(Fornecedor, st.session_state.edit_id)
                if obj:
                    val_n, val_cat, val_t, val_e, val_nif, val_obs = obj.nome, obj.categoria, obj.telefone, obj.email, obj.nif, obj.observacoes
                    val_resp, val_iban = obj.responsavel, obj.iban

            c_form1, c_form2 = st.columns(2)
            with c_form1:
                n = st.text_input("Nome da Empresa / Profissional *", value=val_n, key=f"f_n_{st.session_state.get('form_key', 0)}")
                cat = st.selectbox("Categoria", ["Eletricista", "Canalizador", "Limpeza", "Elevadores", "Seguros", "Geral", "Outro"], index=["Eletricista", "Canalizador", "Limpeza", "Elevadores", "Seguros", "Geral", "Outro"].index(val_cat) if val_cat else 5, key=f"f_cat_{st.session_state.get('form_key', 0)}")
                resp = st.text_input("Responsável de Contacto", value=val_resp, key=f"f_resp_{st.session_state.get('form_key', 0)}")
                t = st.text_input("Telefone", value=val_t, key=f"f_t_{st.session_state.get('form_key', 0)}")
            with c_form2:
                e = st.text_input("Email", value=val_e, key=f"f_e_{st.session_state.get('form_key', 0)}")
                nif_input = st.text_input("NIF", value=val_nif, key=f"f_nif_{st.session_state.get('form_key', 0)}")
                iban_input = st.text_input("IBAN", value=val_iban, key=f"f_iban_{st.session_state.get('form_key', 0)}")
                obs = st.text_area("Observações", value=val_obs, key=f"f_obs_{st.session_state.get('form_key', 0)}")
            
            c1, c2 = st.columns(2)
            if c1.form_submit_button("Guardar Fornecedor"):
                if not n.strip(): st.error("O nome é obrigatório.")
                else:
                    if st.session_state.get("edit_type") == "forn":
                        obj.nome, obj.categoria, obj.telefone, obj.email, obj.nif, obj.observacoes = n, cat, t, e, nif_input, obs
                        obj.responsavel, obj.iban = resp, iban_input
                        st.session_state.toast = ("Fornecedor atualizado!", "✏️")
                    else:
                        session.add(Fornecedor(nome=n, categoria=cat, telefone=t, email=e, nif=nif_input, observacoes=obs, responsavel=resp, iban=iban_input))
                        st.session_state.toast = ("Fornecedor adicionado!", "✅")
                    session.commit(); clear_edit(); st.rerun()
            if c2.form_submit_button("Cancelar"): clear_edit(); st.rerun()

fornecedores = session.query(Fornecedor).all()
if fornecedores:
    with st.container(border=True):
        df_export = pd.DataFrame([{"ID": f.id, "Categoria": f.categoria, "Nome": f.nome, "Telefone": f.telefone, "Email": f.email} for f in fornecedores])
        evento = st.dataframe(df_export, use_container_width=True, hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
    
    if evento.selection.rows:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            id_sel = int(df_export.iloc[evento.selection.rows[0]]["ID"])
            forn_obj = session.get(Fornecedor, id_sel)
            c_info, c_edit, c_del = st.columns([2, 1, 1])
            c_info.info(f":material/push_pin: **{forn_obj.nome}** ({forn_obj.categoria})")
            detalhes = f"**Responsável:** {forn_obj.responsavel if forn_obj.responsavel else 'N/D'} | "
            detalhes += f"**Telefone:** {forn_obj.telefone if forn_obj.telefone else 'N/D'} | "
            detalhes += f"**Email:** {forn_obj.email if forn_obj.email else 'N/D'}\n\n"
            detalhes += f"**NIF:** {forn_obj.nif if forn_obj.nif else 'N/D'} | "
            detalhes += f"**IBAN:** {forn_obj.iban if forn_obj.iban else 'N/D'}\n\n"
            detalhes += f"**Observações:** {forn_obj.observacoes if forn_obj.observacoes else '-'}"
            c_info.write(detalhes)
            
            if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
                if c_edit.button(":material/edit: Editar", use_container_width=True):
                    st.session_state.edit_id = id_sel; st.session_state.edit_type = "forn"; st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()
                if c_del.button(":material/delete: Apagar", use_container_width=True):
                    session.delete(forn_obj); session.commit(); st.session_state.toast = ("Contacto apagado!", "🗑️"); st.rerun()
else: st.info("Ainda não existem fornecedores registados.")