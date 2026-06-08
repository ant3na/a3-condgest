import streamlit as st
import pandas as pd
from sqlalchemy import and_

from db import get_session
from models import Quota
from utils import configurar_sidebar, config, caminho_logo, get_image_base64, gerar_pdf_recibo, enviar_email_real, REPORTLAB_INSTALLED

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.header(":material/receipt_long: Emissão de Recibos")

if st.session_state.perfil == "Admin":
    q_pagas = session.query(Quota).filter(Quota.paga == True).order_by(Quota.data_pagamento.desc()).all()
else:
    q_pagas = session.query(Quota).filter(and_(Quota.paga == True, Quota.condomino_id == st.session_state.condomino_id)).order_by(Quota.data_pagamento.desc()).all()

if not q_pagas: 
    st.warning("Ainda não existem quotas pagas registadas no sistema.")
else:
    st.write(":material/touch_app: **Clique numa linha para gerar e visualizar o recibo de pagamento:**")
    with st.container(border=True):
        df_recibos = pd.DataFrame([{"ID": q.id, "Data Pagamento": q.data_pagamento, "Ref. Mensal": q.mes_ano, "Fração": q.condomino.fracao, "Nome": q.condomino.nome, "Valor": q.valor} for q in q_pagas])
        evento_rec = st.dataframe(df_recibos, use_container_width=True, hide_index=True, column_config={"ID": None, "Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")}, on_select="rerun", selection_mode="single-row")
    
    if evento_rec.selection.rows:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            q = session.get(Quota, int(df_recibos.iloc[evento_rec.selection.rows[0]]["ID"]))
            st.info(f":material/receipt: Recibo selecionado: **{q.valor:.2f}€** referente a **{q.mes_ano}** (Fração {q.condomino.fracao})")

            periodo_seguro = q.mes_ano.replace("/", "-")
            nome_pdf = f"Recibo_{q.condomino.nome.replace(' ', '_')}_{q.condomino.fracao}_{periodo_seguro}"
            nif_display = q.condomino.nif if q.condomino.nif else "N/A"
            img_base64 = get_image_base64(caminho_logo)
            logo_html = f'<img src="data:image/png;base64,{img_base64}" class="logo-img" style="max-height: 80px; width: auto; object-fit: contain;">' if img_base64 else ""

            html_recibo = f"""
            <div style="border: 1px solid #e2e8f0; padding: 40px; border-radius: 12px; background-color: #ffffff; color: #1e293b; max-width: 850px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); font-family: Arial, sans-serif;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
                    <div style="flex: 1;">
                        {logo_html}
                        <h3 style="margin: 15px 0 5px 0; color: #0f172a; font-size: 16px;">{config["NOME_CONDOMINIO"]}</h3>
                        <p style="margin: 0; font-size: 13px; color: #475569; line-height: 1.6;">{config["MORADA_CONDOMINIO"]}<br><strong>NIF:</strong> {config["NIF_CONDOMINIO"]}<br><strong>IBAN:</strong> {config["IBAN_CONDOMINIO"]}</p>
                    </div>
                    <div style="text-align: right; flex: 1;">
                        <h1 style="margin: 0 0 10px 0; color: #0f172a; font-size: 28px;">RECIBO</h1>
                        <p style="margin: 5px 0; font-size: 14px; color: #334155;"><strong>Nº Fatura/Recibo:</strong> #{q.id:05d}</p>
                        <p style="margin: 5px 0; font-size: 14px; color: #334155;"><strong>Data:</strong> {q.data_pagamento}</p>
                    </div>
                </div>
                <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 25px 0;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 30px;">
                    <div style="flex: 1;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 12px; text-transform: uppercase;"><strong>Dados do Condómino</strong></p>
                        <p style="margin: 4px 0; font-size: 15px;"><strong>Nome:</strong> {q.condomino.nome}</p>
                        <p style="margin: 4px 0; font-size: 15px;"><strong>Fração:</strong> {q.condomino.fracao}</p>
                    </div>
                    <div style="flex: 1; padding-top: 26px;">
                        <p style="margin: 4px 0; font-size: 15px;"><strong>NIF:</strong> {nif_display}</p>
                        <p style="margin: 4px 0; font-size: 15px;"><strong>Permilagem:</strong> {q.condomino.permilagem:.2f} ‰</p>
                    </div>
                </div>
                <div style="background-color: #f8fafc; padding: 25px; border-radius: 8px; border-left: 6px solid #2563eb; margin-top: 20px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #334155;">Declaramos que recebemos a quantia de <strong>{q.valor:.2f} €</strong>, referente ao pagamento da quota de condomínio de <strong>{q.mes_ano}</strong>.</p>
                </div>
                <p style="text-align: center; color: #94a3b8; font-size: 11px; margin-top: 40px; border-top: 1px solid #f1f5f9; padding-top: 20px;">
                    <em>Documento processado por computador e sem obrigatoriedade de assinatura.</em>
                </p>
            </div>
            """
            st.markdown(html_recibo.replace("\n", ""), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("#### :material/print: 1. Imprimir / Guardar PDF")
                if REPORTLAB_INSTALLED:
                    pdf_bytes = gerar_pdf_recibo(q)
                    st.download_button(":material/download: Descarregar Recibo (PDF)", data=pdf_bytes, file_name=f"{nome_pdf}.pdf", mime="application/pdf", use_container_width=True)
            with col2:
                st.write("#### :material/mail: 2. Enviar por Email")
                if not st.session_state.modo_leitura:
                    if st.session_state.perfil == "Admin":
                        if st.button(":material/send: Enviar Confirmação Simples", use_container_width=True):
                            if q.condomino.email:
                                corpo = f"Exmo(a) Sr(a) {q.condomino.nome},\nConfirmamos o pagamento da quota de {q.mes_ano}, no valor de {q.valor:.2f} €.\nA Administração."
                                if enviar_email_real(q.condomino.email, f"Confirmação de Pagamento - {q.mes_ano}", corpo): st.toast("Enviado!", icon="✅")
                            else: st.error("Sem email registado.")
                        if REPORTLAB_INSTALLED:
                            if st.button("📧 Enviar Recibo com PDF Anexo", type="primary", use_container_width=True):
                                if q.condomino.email:
                                    corpo = f"Exmo(a) Sr(a) {q.condomino.nome},\nSegue em anexo o recibo oficial em PDF.\nA Administração."
                                    if enviar_email_real(q.condomino.email, f"Recibo Oficial de Pagamento - {q.mes_ano}", corpo, anexo_bytes=pdf_bytes, nome_anexo=f"{nome_pdf}.pdf"): st.toast("Enviado!", icon="🎉")
                                else: st.error("Condómino sem email.")