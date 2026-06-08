import streamlit as st
import pandas as pd
from sqlalchemy import and_

from db import get_session
from models import Condomino, Quota
from utils import configurar_sidebar, config, enviar_email_real, hoje

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.title(":material/payments: Gestão de Quotas")
st.markdown(f"""
<div style="margin-top: -15px; margin-bottom: 20px;">
    <p style="font-size: 18px; color: #64748b; font-weight: 500;">Período referente a {mes_sel} {ano_sel}</p>
</div>
""", unsafe_allow_html=True)

valor_quota_padrao = config.get("VALOR_MENSAL_FIXO", 50.00)

if st.session_state.perfil == "Admin":
    condominos = session.query(Condomino).all()
    dividas_query = session.query(Quota).filter_by(paga=False)
    pagas_query = session.query(Quota).filter(and_(Quota.paga == True, Quota.mes_ano == mes_str))
else:
    condominos = session.query(Condomino).filter_by(id=st.session_state.condomino_id).all()
    dividas_query = session.query(Quota).filter_by(paga=False, condomino_id=st.session_state.condomino_id)
    pagas_query = session.query(Quota).filter(and_(Quota.paga == True, Quota.mes_ano == mes_str, Quota.condomino_id == st.session_state.condomino_id))

if not condominos:
    st.warning("⚠️ **Nenhum condómino registado:** Não existem frações ou moradores registados no sistema. Por favor, vá ao separador **Condóminos** para registar manualmente ou importar o seu ficheiro Excel/CSV.")
    st.stop()

condominos_sem_quota = [c for c in condominos if not session.query(Quota).filter_by(condomino_id=c.id, mes_ano=mes_str).first()]

if st.session_state.perfil == "Admin":
    with st.container(border=True):
        st.subheader(":material/precision_manufacturing: Gerador de Quotas")
        if len(condominos_sem_quota) > 0: st.warning(f"O sistema detetou **{len(condominos_sem_quota)} fração(ões)** sem quota processada neste mês.")
        else: st.success(f"As quotas do mês {mes_str} já estão processadas.")
        if not st.session_state.modo_leitura:
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f":material/bolt: Gerar Quotas Apenas de {mes_str}", use_container_width=True):
                    if len(condominos_sem_quota) > 0:
                        for c in condominos_sem_quota: session.add(Quota(condomino_id=c.id, mes_ano=mes_str, valor=valor_quota_padrao, paga=False))
                        session.commit(); st.session_state.toast = (f"Quotas de {mes_str} geradas!", "✅"); st.rerun()
                        registar_atividade(session, st.session_state.username, "Registar Pagamento de Quota", f"Quota de {q.mes_ano} paga pela fração {q.condomino.fracao} no valor de {q.valor}€")
                    else: st.info("Não há quotas em falta.")
            with col2:
                if st.button(f":material/calendar_month: Gerar para Todo o Ano de {ano_sel}", use_container_width=True, type="primary"):
                    novas_quotas = 0
                    for c in condominos:
                        for m in range(1, 13):
                            m_str = f"{m:02d}/{ano_sel}"
                            if not session.query(Quota).filter_by(condomino_id=c.id, mes_ano=m_str).first():
                                session.add(Quota(condomino_id=c.id, mes_ano=m_str, valor=valor_quota_padrao, paga=False))
                                novas_quotas += 1
                    if novas_quotas > 0: session.commit(); st.session_state.toast = (f"{novas_quotas} quotas geradas!", "🎉")
                        registar_atividade(session, st.session_state.username, "Gerar Quotas Anuais", f"Quotas geradas para o ano de {ano_sel}")
                    else: st.session_state.toast = (f"As quotas de {ano_sel} já estavam geradas.", "ℹ️")
                    st.rerun()
else:
    if len(condominos_sem_quota) > 0: st.info("A sua quota deste mês ainda não foi processada.")
    else: st.success(f"✅ As suas quotas referentes a {mes_str} já se encontram processadas.")

st.markdown("<br>", unsafe_allow_html=True)
tab_dividas, tab_pagas = st.tabs([":material/error: Quotas em Dívida (A Cobrar)", f":material/check_circle: Quotas Recebidas [{mes_sel}]"])

with tab_dividas:
    dividas = dividas_query.order_by(Quota.mes_ano).all()
    
    if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura and dividas:
        with st.expander(":material/forward_to_inbox: Enviar Avisos em Lote", expanded=False):
            st.write("Notifique todos os condóminos com dívidas ativas num só clique.")
            if st.button("Disparar Avisos para Todos os Devedores", use_container_width=True, type="primary"):
                emails_enviados = 0
                for d in dividas:
                    if d.condomino.email:
                        corpo_email = f"Exmo(a) Sr(a) {d.condomino.nome},\n\nVerificamos que se encontra a pagamento a quota de {d.mes_ano} no valor de {d.valor:.2f} €.\n\nPor favor, proceda à transferência para o seguinte IBAN: {config.get('IBAN_CONDOMINIO', 'N/D')}\n\nA Administração."
                        if enviar_email_real(d.condomino.email, f"Aviso de Pagamento de Quota - {d.mes_ano}", corpo_email):
                            emails_enviados += 1
                if emails_enviados > 0: st.success(f"{emails_enviados} avisos enviados com sucesso!")
                else: st.warning("Nenhum aviso enviado. Verifique se os condóminos devedores têm email registado.")

    if dividas:
        with st.container(border=True):
            df_dividas = pd.DataFrame([{"ID": d.id, "Mês Ref": d.mes_ano, "Fração": d.condomino.fracao, "Nome": d.condomino.nome, "Valor": d.valor} for d in dividas])
            evento_divida = st.dataframe(df_dividas, use_container_width=True, hide_index=True, column_config={"ID": None, "Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")}, on_select="rerun", selection_mode="single-row")
        if evento_divida.selection.rows:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                quota_obj = session.get(Quota, int(df_dividas.iloc[evento_divida.selection.rows[0]]["ID"]))
                st.info(f":material/push_pin: Selecionado: **Fração {quota_obj.condomino.fracao}** ({quota_obj.mes_ano}) - **{quota_obj.valor:.2f} €**")
                col_pagar, col_aviso = st.columns(2)
                if not st.session_state.modo_leitura:
                    if col_pagar.button(":material/done: Marcar como Paga", use_container_width=True):
                        quota_obj.paga = True; quota_obj.data_pagamento = hoje.strftime("%Y-%m-%d"); session.commit(); st.rerun()
                    if st.session_state.perfil == "Admin":
                        with col_aviso.popover(":material/mail: Enviar Aviso Individual"):
                            corpo_email = f"Exmo(a) Sr(a) {quota_obj.condomino.nome},\n\nEncontra-se a pagamento a quota de {quota_obj.mes_ano} no valor de {quota_obj.valor:.2f} €.\n\nPor favor, proceda à transferência para o seguinte IBAN: {config.get('IBAN_CONDOMINIO', 'N/D')}\n\nA Administração."
                            st.markdown(f"**Mensagem:**\n\n{corpo_email}")
                            if st.button("Confirmar Envio", key=f"mail_aviso_{quota_obj.id}", use_container_width=True):
                                if quota_obj.condomino.email:
                                    if enviar_email_real(quota_obj.condomino.email, f"Aviso de Pagamento - {quota_obj.mes_ano}", corpo_email): st.toast("Enviado!", icon="✅")
                                else: st.error("Sem email registado.")
    else: st.success("🎉 Não existem quotas em dívida.")

with tab_pagas:
    pagas = pagas_query.all()
    if pagas:
        with st.container(border=True):
            df_pagas = pd.DataFrame([{"Data": p.data_pagamento, "Referência": p.mes_ano, "Fração": p.condomino.fracao, "Nome": p.condomino.nome, "Valor": p.valor} for p in pagas])
            st.dataframe(df_pagas, use_container_width=True, hide_index=True, column_config={"Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")})
