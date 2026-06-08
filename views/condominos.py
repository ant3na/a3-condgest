import streamlit as st
import pandas as pd
from sqlalchemy import func

from db import get_session
from models import Condomino
from utils import configurar_sidebar

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

def clear_edit():
    st.session_state.edit_id = None
    st.session_state.edit_type = None
    st.session_state.form_key = st.session_state.get('form_key', 0) + 1 

st.header(":material/group: Gestão de Condóminos")

if not st.session_state.modo_leitura and st.session_state.perfil == "Admin":
    with st.expander(":material/upload_file: Importar Moradores via Excel/CSV"):
        st.write("Faça upload de um ficheiro CSV ou Excel contendo as seguintes colunas (exatamente com estes nomes): `Nome,Fração,NIF,Telefone,Email,Permilagem`.")
        ficheiro_import = st.file_uploader("Escolher ficheiro", type=["csv", "xlsx"], key=f"file_up_{st.session_state.get('form_key', 0)}")
        if ficheiro_import is not None:
            if st.button("Processar Importação", use_container_width=True):
                try:
                    if ficheiro_import.name.endswith(".csv"): 
                        try:
                            df_imp = pd.read_csv(ficheiro_import, encoding="utf-8", sep=None, engine="python")
                        except UnicodeDecodeError:
                            ficheiro_import.seek(0)
                            df_imp = pd.read_csv(ficheiro_import, encoding="latin1", sep=None, engine="python")
                    else: 
                        df_imp = pd.read_excel(ficheiro_import)
                    
                    novos = 0
                    for _, row in df_imp.iterrows():
                        fracao = str(row.get("Fração", "")).strip()
                        if fracao and fracao != "nan":
                            existe = session.query(Condomino).filter_by(fracao=fracao).first()
                            if not existe:
                                novo_c = Condomino(
                                    nome=str(row.get("Nome", "Sem Nome")).strip(),
                                    fracao=fracao,
                                    nif=str(row.get("NIF", "")).replace(".0","").replace("nan",""),
                                    telefone=str(row.get("Telefone", "")).replace(".0","").replace("nan",""),
                                    email=str(row.get("Email", "")).strip().replace("nan",""),
                                    permilagem=float(row.get("Permilagem", 0.0)) if pd.notna(row.get("Permilagem")) else 0.0
                                )
                                session.add(novo_c)
                                novos += 1
                    if novos > 0:
                        session.commit()
                        registar_atividade(session, st.session_state.username, "Importar Condóminos", f"Importados {novos} novos registos via ficheiro")
                        st.success(f"{novos} frações importadas com sucesso!")
                        st.session_state.form_key = st.session_state.get('form_key', 0) + 1
                    else:
                        st.warning("Não foram importadas frações (já existem ou ficheiro sem dados válidos).")
                except Exception as e:
                    st.error(f"Erro ao processar o ficheiro. Detalhe técnico: {e}")

conds = session.query(Condomino).all()
total_permilagem = session.query(func.sum(Condomino.permilagem)).scalar() or 0.0
col_kpi1, col_kpi2 = st.columns([3, 1])
col_kpi1.info(f"Permilagem Total Registada: **{total_permilagem:.2f} / 1000**")

if not st.session_state.modo_leitura:
    title_form = ":material/edit: Editar Condómino" if st.session_state.get("edit_type") == "cond" else ":material/person_add: Registo Manual"
    with st.expander(title_form, expanded=(st.session_state.get("edit_type") == "cond")):
        with st.form("f_cond"):
            val_n, val_f, val_nif, val_t, val_e, val_p = "", "", "", "", "", 0.0
            if st.session_state.get("edit_type") == "cond" and st.session_state.get("edit_id"):
                obj = session.get(Condomino, st.session_state.edit_id)
                if obj: val_n, val_f, val_nif, val_t, val_e, val_p = obj.nome, obj.fracao, obj.nif, obj.telefone, obj.email, obj.permilagem

            c_form1, c_form2 = st.columns(2)
            with c_form1:
                n = st.text_input("Nome do Proprietário", value=val_n, key=f"c_n_{st.session_state.get('form_key', 0)}")
                f = st.text_input("Fração (Ex: 1º Esq)", value=val_f, key=f"c_f_{st.session_state.get('form_key', 0)}")
                p = st.number_input("Permilagem (ex: 50.5)", value=float(val_p), min_value=0.0, max_value=1000.0, format="%.2f", key=f"c_p_{st.session_state.get('form_key', 0)}")
            with c_form2:
                nif_input = st.text_input("NIF", value=val_nif, key=f"c_nif_{st.session_state.get('form_key', 0)}")
                t = st.text_input("Telefone", value=val_t, key=f"c_t_{st.session_state.get('form_key', 0)}")
                e = st.text_input("Email", value=val_e, key=f"c_e_{st.session_state.get('form_key', 0)}")
            
            c1, c2 = st.columns(2)
            if c1.form_submit_button("Guardar"):
                if st.session_state.get("edit_type") == "cond":
                    obj.nome, obj.fracao, obj.nif, obj.telefone, obj.email, obj.permilagem = n, f, nif_input, t, e, p
                    st.session_state.toast = ("Condómino atualizado!", "✏️")
                else:
                    session.add(Condomino(nome=n, fracao=f, nif=nif_input, telefone=t, email=e, permilagem=p))
                    st.session_state.toast = ("Condómino adicionado!", "✅")
                session.commit(); 
                registar_atividade(session, st.session_state.username, "Guardar Condómino", f"Registo guardado para a fração {f} ({n})")
                clear_edit(); st.rerun()
            if c2.form_submit_button("Cancelar"): clear_edit(); st.rerun()

if conds:
    with st.container(border=True):
        df_export = pd.DataFrame([{"ID": c.id, "Fração": c.fracao, "Nome": c.nome, "NIF": c.nif, "Permilagem": c.permilagem, "Telefone": c.telefone, "Email": c.email} for c in conds])
        evento = st.dataframe(df_export, use_container_width=True, hide_index=True, column_config={"ID": None, "Permilagem": st.column_config.NumberColumn("Permilagem (‰)", format="%.2f ‰")}, on_select="rerun", selection_mode="single-row")
    
    if evento.selection.rows:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            id_sel = int(df_export.iloc[evento.selection.rows[0]]["ID"])
            cond_obj = session.get(Condomino, id_sel)
            c_info, c_edit, c_del = st.columns([2, 1, 1])
            c_info.info(f":material/push_pin: Selecionado: **{cond_obj.fracao} - {cond_obj.nome}**")
            if not st.session_state.modo_leitura:
                if c_edit.button(":material/edit: Editar Fração", use_container_width=True):
                    st.session_state.edit_id = id_sel; st.session_state.edit_type = "cond"; st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()
                if c_del.button(":material/delete: Apagar Registo", use_container_width=True):
                    session.delete(cond_obj); 
                    session.commit(); 
                    registar_atividade(session, st.session_state.username, "Apagar Condómino", f"Registo apagado para a fração {cond_obj.fracao}")
                    st.session_state.toast = ("Registo apagado!", "🗑️"); st.rerun()
else: st.info("Ainda não existem condóminos registados.")
