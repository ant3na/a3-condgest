import streamlit as st
import pandas as pd
from sqlalchemy import func, and_

from db import get_session
from models import Orcamento, Movimento, Quota, Condomino
from utils import configurar_sidebar, gerar_pdf_extrato, gerar_pdf_relatorio_anual, enviar_email_real, hoje, REPORTLAB_INSTALLED

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.header(":material/account_balance: Finanças e Fluxo de Caixa")

tab_mes, tab_ano = st.tabs([f"📅 Extrato Mensal ({mes_sel})", f"📈 Relatório Anual (Fecho de Contas {ano_sel})"])

with tab_mes:
    if not st.session_state.modo_leitura and st.session_state.perfil == "Admin":
        orc = session.query(Orcamento).filter_by(ano=ano_sel).first()
        with st.expander(f":material/assignment: Definir Orçamento Anual de {ano_sel}", expanded=(not orc)):
            with st.form("f_orc"):
                v_orc = st.number_input(f"Valor do Orçamento Aprovado (€)", value=orc.valor_anual if orc else 0.0, step=100.0, key=f"o_v_{st.session_state.get('form_key', 0)}")
                if st.form_submit_button("Guardar Orçamento"):
                    if orc: orc.valor_anual = v_orc
                    else: session.add(Orcamento(ano=ano_sel, valor_anual=v_orc))
                    session.commit(); st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()

    orc = session.query(Orcamento).filter_by(ano=ano_sel).first()
    if orc and orc.valor_anual > 0:
        with st.container(border=True):
            despesas_ano = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Despesa", Movimento.data.startswith(str(ano_sel)))).scalar() or 0.0
            pct = (despesas_ano / orc.valor_anual) * 100
            st.write(f"**Execução Orçamental ({ano_sel}):** {despesas_ano:.2f}€ gastos de {orc.valor_anual:.2f}€ ({pct:.1f}%)")
            st.progress(min(pct / 100, 1.0))

    if not st.session_state.modo_leitura and st.session_state.perfil == "Admin":
        st.markdown("<br>", unsafe_allow_html=True)
        c_add_man, c_add_imp = st.columns(2)
        
        with c_add_man:
            with st.expander(":material/add_circle: Lançar Nova Despesa ou Receita", expanded=False):
                with st.form("f_mov"):
                    t = st.radio("Tipo de Lançamento", ["Despesa", "Receita"], horizontal=True, key=f"m_t_{st.session_state.get('form_key', 0)}")
                    d = st.text_input("Descrição *", key=f"m_d_{st.session_state.get('form_key', 0)}")
                    v = st.number_input("Valor (€) *", min_value=0.00, value=0.00, step=10.0, format="%.2f", key=f"m_v_{st.session_state.get('form_key', 0)}")
                    dt = st.date_input("Data do Movimento", value=hoje, key=f"m_dt_{st.session_state.get('form_key', 0)}")
                    if st.form_submit_button("Registar Lançamento"):
                        if not d.strip(): st.error("⚠️ O preenchimento da Descrição é obrigatório!")
                        elif v <= 0.0: st.error("⚠️ O valor do lançamento tem de ser superior a 0,00 €!")
                        else:
                            session.add(Movimento(tipo=t, descricao=d, valor=v, data=dt.strftime("%Y-%m-%d")))
                            session.commit(); st.session_state.toast = ("Lançamento registado com sucesso!", "✅")
                            st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()

        with c_add_imp:
            with st.expander(":material/upload_file: Importar Extrato Bancário", expanded=False):
                st.write("Faça upload de um ficheiro com as colunas exatas: `Tipo,Descrição,Valor,Data`. O Tipo deve ser **Despesa** ou **Receita**.")
                ficheiro_import_fin = st.file_uploader("Escolher ficheiro financeiro", type=["csv", "xlsx"], key=f"file_up_fin_{st.session_state.get('form_key', 0)}")
                if ficheiro_import_fin is not None:
                    if st.button("Processar Importação", use_container_width=True, type="primary"):
                        try:
                            if ficheiro_import_fin.name.endswith(".csv"): 
                                try:
                                    df_imp = pd.read_csv(ficheiro_import_fin, encoding="utf-8", sep=None, engine="python")
                                except UnicodeDecodeError:
                                    ficheiro_import_fin.seek(0)
                                    df_imp = pd.read_csv(ficheiro_import_fin, encoding="latin1", sep=None, engine="python")
                            else: 
                                df_imp = pd.read_excel(ficheiro_import_fin)
                            
                            novos_movs = 0
                            for _, row in df_imp.iterrows():
                                tipo = str(row.get("Tipo", "")).strip().capitalize()
                                descricao = str(row.get("Descrição", "")).strip()
                                valor_raw = row.get("Valor", 0.0)
                                valor = pd.to_numeric(str(valor_raw).replace(",", "."), errors="coerce")
                                data_raw = row.get("Data", "")
                                data_mov = str(data_raw)[:10].strip() if pd.notna(data_raw) and str(data_raw).strip() != "" else hoje.strftime("%Y-%m-%d")

                                if tipo in ["Despesa", "Receita"] and descricao and pd.notna(valor) and float(valor) > 0:
                                    session.add(Movimento(tipo=tipo, descricao=descricao, valor=float(valor), data=data_mov))
                                    novos_movs += 1
                                    
                            if novos_movs > 0:
                                session.commit()
                                st.success(f"{novos_movs} movimentos importados com sucesso!")
                                st.session_state.form_key = st.session_state.get('form_key', 0) + 1
                                st.rerun()
                            else:
                                st.warning("Não foram importados registos válidos.")
                        except Exception as e:
                            st.error(f"Erro ao processar o ficheiro: {e}")

    st.markdown("<br>", unsafe_allow_html=True)
    movs = session.query(Movimento).filter(and_(Movimento.data >= str_inicio, Movimento.data < str_fim)).all()
    q_ant = session.query(func.sum(Quota.valor)).filter(and_(Quota.paga == True, Quota.data_pagamento < str_inicio)).scalar() or 0.0
    rec_ant = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Receita", Movimento.data < str_inicio)).scalar() or 0.0
    desp_ant = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Despesa", Movimento.data < str_inicio)).scalar() or 0.0
    saldo_anterior = (q_ant + rec_ant) - desp_ant
    q_atual = session.query(func.sum(Quota.valor)).filter(and_(Quota.paga == True, Quota.data_pagamento >= str_inicio, Quota.data_pagamento < str_fim)).scalar() or 0.0

    extrato_data = [{"ID": "-", "Data": "-", "Tipo": "Receita (Quotas)", "Descrição": "Soma Quotas Mensais", "Valor": q_atual}]
    if movs: extrato_data.extend([{"ID": m.id, "Data": m.data, "Tipo": m.tipo, "Descrição": m.descricao, "Valor": m.valor} for m in movs])
    df_extrato = pd.DataFrame(extrato_data)

    col_tit, col_btn = st.columns([3, 1])
    with col_tit:
        st.subheader(f"Movimentos de {mes_sel} {ano_sel}")
        st.write(f"**Saldo Transitado do Mês Anterior:** {saldo_anterior:.2f} €")
        st.write(f"**(+) Total Quotas Recebidas no Mês:** {q_atual:.2f} €")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if REPORTLAB_INSTALLED:
            pdf_bytes = gerar_pdf_extrato(df_extrato, mes_sel, ano_sel, saldo_anterior)
            if pdf_bytes: st.download_button(":material/picture_as_pdf: Exportar PDF", data=pdf_bytes, file_name=f"Extrato_{mes_sel}_{ano_sel}.pdf", mime="application/pdf", use_container_width=True)
    
    if movs or q_atual > 0:
        with st.container(border=True):
            evento_fin = st.dataframe(df_extrato, use_container_width=True, hide_index=True, column_config={"ID": None, "Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")}, on_select="rerun", selection_mode="single-row")
        if evento_fin.selection.rows and not st.session_state.modo_leitura and st.session_state.perfil == "Admin":
            id_mov = df_extrato.iloc[evento_fin.selection.rows[0]]["ID"]
            if id_mov != "-": 
                with st.container(border=True):
                    mov_obj = session.get(Movimento, int(id_mov))
                    if st.button(f":material/delete: Apagar {mov_obj.descricao}", use_container_width=True): session.delete(mov_obj); session.commit(); st.rerun()

with tab_ano:
    st.subheader(f"Resumo Financeiro Global - {ano_sel}")
    str_inicio_ano = f"{ano_sel}-01-01"
    str_fim_ano = f"{ano_sel+1}-01-01"
    
    q_ant_ano = session.query(func.sum(Quota.valor)).filter(and_(Quota.paga == True, Quota.data_pagamento < str_inicio_ano)).scalar() or 0.0
    rec_ant_ano = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Receita", Movimento.data < str_inicio_ano)).scalar() or 0.0
    desp_ant_ano = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Despesa", Movimento.data < str_inicio_ano)).scalar() or 0.0
    saldo_anterior_ano = (q_ant_ano + rec_ant_ano) - desp_ant_ano
    
    q_atual_ano = session.query(func.sum(Quota.valor)).filter(and_(Quota.paga == True, Quota.data_pagamento >= str_inicio_ano, Quota.data_pagamento < str_fim_ano)).scalar() or 0.0
    rec_atual_ano = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Receita", Movimento.data >= str_inicio_ano, Movimento.data < str_fim_ano)).scalar() or 0.0
    desp_atual_ano = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Despesa", Movimento.data >= str_inicio_ano, Movimento.data < str_fim_ano)).scalar() or 0.0
    saldo_final_ano = saldo_anterior_ano + q_atual_ano + rec_atual_ano - desp_atual_ano
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo do Ano Anterior", f"{saldo_anterior_ano:.2f} €")
    c2.metric("Total Quotas+Receitas", f"{q_atual_ano + rec_atual_ano:.2f} €")
    c3.metric("Total Despesas", f"{desp_atual_ano:.2f} €")
    c4.metric("Saldo Final do Ano", f"{saldo_final_ano:.2f} €")
    
    despesas_ano_lista = session.query(Movimento).filter(and_(Movimento.tipo == "Despesa", Movimento.data >= str_inicio_ano, Movimento.data < str_fim_ano)).all()
    df_despesas_ano = pd.DataFrame([{"Descrição": d.descricao, "Valor": d.valor} for d in despesas_ano_lista])
    if not df_despesas_ano.empty:
        df_desp_agrupadas = df_despesas_ano.groupby("Descrição")["Valor"].sum().reset_index().sort_values(by="Valor", ascending=False)
    else:
        df_desp_agrupadas = pd.DataFrame(columns=["Descrição", "Valor"])
        
    st.markdown("<br>", unsafe_allow_html=True)
    col_pdf, col_mail = st.columns(2)
    
    if REPORTLAB_INSTALLED:
        pdf_bytes_anual = gerar_pdf_relatorio_anual(ano_sel, saldo_anterior_ano, q_atual_ano, rec_atual_ano, desp_atual_ano, df_desp_agrupadas)
        with col_pdf:
            st.download_button("📥 Descarregar Relatório (PDF)", data=pdf_bytes_anual, file_name=f"Relatorio_{ano_sel}.pdf", mime="application/pdf", use_container_width=True)
        
        with col_mail:
            if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
                if st.button("📧 Enviar por Email a Todos", use_container_width=True, type="primary"):
                    condominos_com_email = session.query(Condomino).filter(Condomino.email.isnot(None), Condomino.email != "").all()
                    emails_enviados = 0
                    for c in condominos_com_email:
                        corpo_email = f"Exmo(a) Sr(a) {c.nome},\n\nJunto enviamos o Relatório Anual referente a {ano_sel}.\n\nA Administração."
                        if enviar_email_real(c.email, f"Relatório de Contas - {ano_sel}", corpo_email, anexo_bytes=pdf_bytes_anual, nome_anexo=f"Relatorio_{ano_sel}.pdf"):
                            emails_enviados += 1
                    if emails_enviados > 0: st.success(f"Enviado a {emails_enviados} condóminos com sucesso!")
                    else: st.warning("Não existem condóminos com email registado.")
    
    with st.container(border=True):
        st.write("**Detalhamento das Despesas do Ano:**")
        if not df_desp_agrupadas.empty:
            st.dataframe(df_desp_agrupadas, use_container_width=True, hide_index=True, column_config={"Valor": st.column_config.NumberColumn("Valor Total Pago no Ano (€)", format="%.2f €")})
        else:
            st.info("Ainda não existem despesas registadas neste ano civil.")