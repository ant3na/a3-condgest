import streamlit as st
import pandas as pd
from werkzeug.security import generate_password_hash

# Importar da nossa base de dados e utilitários
from db import get_session
from models import Condomino, Quota, Utilizador
from utils import configurar_sidebar, config, registar_atividade

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

if not st.session_state.condomino_id:
    st.error("O seu utilizador não está associado a nenhuma fração.")
    st.stop()

cond = session.get(Condomino, st.session_state.condomino_id)
st.title(f":material/home: Bem-vindo, {cond.nome}!")
st.subheader(f"Fração: {cond.fracao} | Permilagem: {cond.permilagem}‰")

if config.get("AVISO_ATIVO") and config.get("AVISO_GLOBAL"):
    st.info(f"📢 **Aviso da Administração:**\n\n{config['AVISO_GLOBAL']}")

with st.expander(":material/key: Alterar a minha Password", expanded=False):
    with st.form("form_pwd"):
        nova_pwd = st.text_input("Nova Password", type="password", key=f"pwd1_{st.session_state.get('form_key', 0)}")
        conf_pwd = st.text_input("Confirmar Nova Password", type="password", key=f"pwd2_{st.session_state.get('form_key', 0)}")
        if st.form_submit_button("Atualizar Segurança"):
            if nova_pwd != conf_pwd: st.error("As passwords não coincidem!")
            elif len(nova_pwd) < 4: st.error("A password deve ter pelo menos 4 caracteres.")
            else:
                utilizador_ativo = session.get(Utilizador, st.session_state.user_id)
                utilizador_ativo.password_hash = generate_password_hash(nova_pwd)
                session.commit()
                registar_atividade(session, st.session_state.username, "Alterar Password", "O utilizador atualizou a sua própria credencial de acesso")
                st.session_state.toast = ("Password atualizada com sucesso!", "✅")
                if "form_key" in st.session_state: st.session_state.form_key += 1
                st.rerun()

dividas = session.query(Quota).filter_by(condomino_id=cond.id, paga=False).all()
if dividas:
    divida_total = sum([q.valor for q in dividas])
    st.warning(f"Tem um valor total em dívida de **{divida_total:.2f} €**.")
    with st.expander(":material/account_balance: Dados para Pagamento", expanded=True):
        st.write("Por favor, utilize o seguinte IBAN para regularizar a sua situação:")
        st.code(f"IBAN: {config.get('IBAN_CONDOMINIO', 'Não configurado')}", language="text")
else:
    st.success("Tudo em dia! Obrigado pela sua contribuição.")

st.markdown("<br>", unsafe_allow_html=True)
with st.container(border=True):
    st.write("### :material/receipt_long: A sua Conta Corrente")
    quotas = session.query(Quota).filter_by(condomino_id=cond.id).order_by(Quota.mes_ano.desc()).all()
    if quotas:
        df_q = pd.DataFrame([{"Referência": q.mes_ano, "Valor": q.valor, "Estado": "🟢 Pago" if q.paga else "🔴 Em Dívida", "Data Pagamento": q.data_pagamento if q.paga else "-"} for q in quotas])
        st.dataframe(df_q, use_container_width=True, hide_index=True, column_config={"Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")})
    else: st.info("Ainda não existem registos na sua conta.")
