import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from sqlalchemy import func, and_

from db import get_session
from models import Condomino, Quota, Movimento, Ocorrencia, Orcamento, Assembleia, Sondagem
from utils import configurar_sidebar, config, hoje

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.title(":material/dashboard: Dashboard")
st.markdown(f"""
<div style="margin-top: -15px; margin-bottom: 20px;">
    <p style="font-size: 18px; color: #64748b; font-weight: 500;">Período referente a {mes_sel} {ano_sel}</p>
</div>
""", unsafe_allow_html=True)

if config.get("AVISO_ATIVO") and config.get("AVISO_GLOBAL"):
    st.info(f"📢 **Aviso da Administração:**\n\n{config['AVISO_GLOBAL']}")

col1, col2, col3, col4 = st.columns(4)
total_cond = session.query(Condomino).count()
saldo_total = (session.query(func.sum(Quota.valor)).filter_by(paga=True).scalar() or 0.0) + (session.query(func.sum(Movimento.valor)).filter_by(tipo="Receita").scalar() or 0.0) - (session.query(func.sum(Movimento.valor)).filter_by(tipo="Despesa").scalar() or 0.0)

valor_divida = session.query(func.sum(Quota.valor)).filter_by(paga=False).scalar() or 0.0
dividas_ativas = session.query(Quota).filter_by(paga=False).count()
ocs_pendentes = session.query(Ocorrencia).filter_by(resolvida=False).count()

cor_delta_divida = "normal" if dividas_ativas == 0 else "inverse"

col1.metric("Frações Registadas", total_cond)
col2.metric("Saldo de Caixa", f"{saldo_total:.2f} €")
col3.metric("Valor em Dívida", f"{valor_divida:.2f} €", f"{dividas_ativas} quotas atrasadas", delta_color=cor_delta_divida)
col4.metric("Ocorrências Abertas", ocs_pendentes)
st.markdown("<br>", unsafe_allow_html=True)

tab_geral, tab_fracoes, tab_devedores = st.tabs([":material/pie_chart: Visão Global", ":material/bar_chart: Histórico de Receitas", ":material/warning: Análise de Incumprimento"])
meses_map = {"01":"Jan", "02":"Fev", "03":"Mar", "04":"Abr", "05":"Mai", "06":"Jun", "07":"Jul", "08":"Ago", "09":"Set", "10":"Out", "11":"Nov", "12":"Dez"}

with tab_geral:
    c1, c2, c3 = st.columns(3)
    
    with c1:
        with st.container(border=True):
            st.subheader(f"Estado das Quotas [{ano_sel}]")
            quotas_ano = session.query(Quota).filter(Quota.mes_ano.endswith(str(ano_sel))).all()
            if quotas_ano:
                df_q = pd.DataFrame([{"Estado": "Pagas", "Valor": q.valor} if q.paga else {"Estado": "Em Dívida", "Valor": q.valor} for q in quotas_ano])
                fig1 = px.pie(df_q.groupby("Estado").sum().reset_index(), values="Valor", names="Estado", hole=0.4, color="Estado", color_discrete_map={"Pagas":"#2563eb", "Em Dívida":"#ef4444"})
                fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
                
                total_gerado = sum(q.valor for q in quotas_ano)
                total_pago = sum(q.valor for q in quotas_ano if q.paga)
                if total_gerado > 0:
                    taxa = (total_pago / total_gerado) * 100
                    st.write(f"**Taxa de Cobrança Anual:** {taxa:.1f}%")
                    st.progress(min(taxa / 100, 1.0))
            else: st.info("Sem quotas geradas neste ano.")

    with c2:
        with st.container(border=True):
            st.subheader(f"Receitas / Despesas [{ano_sel}]")
            dados_grafico = [{"Mês": m.data[5:7], "Tipo": m.tipo, "Valor": m.valor} for m in session.query(Movimento).filter(Movimento.data.startswith(str(ano_sel))).all()]
            dados_grafico.extend([{"Mês": q.data_pagamento[5:7], "Tipo": "Receita", "Valor": q.valor} for q in session.query(Quota).filter(and_(Quota.paga == True, Quota.data_pagamento.startswith(str(ano_sel)))).all() if q.data_pagamento])
            if dados_grafico:
                df_fin_grouped = pd.DataFrame(dados_grafico).groupby(["Mês", "Tipo"]).sum().reset_index()
                df_fin_grouped["Mês_Nome"] = df_fin_grouped["Mês"].map(meses_map)
                fig2 = px.bar(df_fin_grouped, x="Mês_Nome", y="Valor", color="Tipo", barmode="group", color_discrete_map={"Receita":"#2563eb", "Despesa":"#ef4444"}, text_auto=".2f")
                fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text="", margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
            else: st.info("Sem dados financeiros registados.")
            
    with c3:
        with st.container(border=True):
            st.subheader(f"Orçamento [{ano_sel}]")
            orc = session.query(Orcamento).filter_by(ano=ano_sel).first()
            despesas_ano_lista = session.query(Movimento).filter(and_(Movimento.tipo == "Despesa", Movimento.data.startswith(str(ano_sel)))).all()
            despesas_ano = sum(d.valor for d in despesas_ano_lista)
            
            if orc and orc.valor_anual > 0:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=despesas_ano,
                    number={"valueformat": ".2f", "suffix": " €"},
                    domain={"x": [0, 1], "y": [0, 1]},
                    gauge={
                        "axis": {"range": [None, orc.valor_anual], "tickwidth": 1},
                        "bar": {"color": "#1e293b"},
                        "bgcolor": "white",
                        "steps": [
                            {"range": [0, orc.valor_anual * 0.7], "color": "#bbf7d0"},
                            {"range": [orc.valor_anual * 0.7, orc.valor_anual * 0.9], "color": "#fef08a"},
                            {"range": [orc.valor_anual * 0.9, orc.valor_anual * 1.5], "color": "#fecaca"}
                        ],
                        "threshold": {
                            "line": {"color": "red", "width": 3},
                            "thickness": 0.75,
                            "value": orc.valor_anual
                        }
                    }
                ))
                fig_gauge.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", 
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=30, b=10, l=20, r=20),
                    height=250
                )
                st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})
                
                percentagem = (despesas_ano / orc.valor_anual) * 100
                if percentagem > 100:
                    st.error(f"⚠️ Orçamento excedido em {percentagem - 100:.1f}%")
                elif percentagem > 90:
                    st.warning("⚠️ Orçamento quase no limite!")
            else: 
                st.info("⚠️ Orçamento não definido. Vá a 'Finanças' para definir o valor aprovado para este ano.")

    st.markdown("<br>", unsafe_allow_html=True)
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    
    with r2_c1:
        with st.container(border=True):
            st.subheader("🍩 Categoria de Despesas")
            if despesas_ano_lista:
                df_desp = pd.DataFrame([{"Categoria": d.descricao, "Valor": d.valor} for d in despesas_ano_lista])
                df_desp_grouped = df_desp.groupby("Categoria").sum().reset_index()
                
                fig_donut = px.pie(df_desp_grouped, values="Valor", names="Categoria", hole=0.5, color_discrete_sequence=px.colors.qualitative.Safe)
                fig_donut.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", 
                    plot_bgcolor="rgba(0,0,0,0)", 
                    margin=dict(t=10, b=10, l=10, r=10),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("Não existem despesas lançadas este ano para categorizar.")
                
    with r2_c2:
        with st.container(border=True):
            st.subheader("📋 Ocorrências Pendentes")
            ocs_lista = session.query(Ocorrencia).filter_by(resolvida=False).order_by(Ocorrencia.id.desc()).limit(5).all()
            if ocs_lista:
                df_ocs_dash = pd.DataFrame([{"Data": o.data_criacao, "Assunto": o.titulo} for o in ocs_lista])
                st.dataframe(df_ocs_dash, hide_index=True, use_container_width=True)
                st.caption("Aceda ao menu 'Ocorrências' para gerir ou resolver estes pedidos.")
            else:
                st.success("🎉 Excelente! Todas as ocorrências do prédio estão resolvidas.")
                
    with r2_c3:
        with st.container(border=True):
            st.subheader("📅 Agenda & Comunidade")
            ass_futuras = session.query(Assembleia).filter_by(realizada=False).order_by(Assembleia.data_agendada).limit(2).all()
            sond_ativas = session.query(Sondagem).filter_by(ativa=True).count()
            
            alertas_encontrados = False
            
            if ass_futuras:
                alertas_encontrados = True
                for a in ass_futuras:
                    try:
                        d_ass = datetime.strptime(a.data_agendada, "%Y-%m-%d").date()
                        dias_restantes = (d_ass - hoje).days
                        if dias_restantes == 0:
                            st.warning(f"🚨 **Assembleia HOJE:** '{a.titulo}'")
                        elif dias_restantes > 0:
                            st.info(f"⏳ Faltam **{dias_restantes} dias** para: '{a.titulo}' ({d_ass.strftime('%d/%m/%Y')})")
                        else:
                            st.error(f"⚠️ Reunião atrasada por realizar: '{a.titulo}'")
                    except Exception:
                        st.info(f"📅 Reunião Agendada: '{a.titulo}' ({a.data_agendada})")
            
            if sond_ativas > 0:
                alertas_encontrados = True
                st.success(f"🗳️ Existem **{sond_ativas} votações ativas** a decorrer.")
                
            if not alertas_encontrados:
                st.info("Sem reuniões agendadas ou votações em curso de momento.")

with tab_fracoes:
    with st.container(border=True):
        st.subheader(f"Evolução de Pagamentos por Fração [{ano_sel}]")
        quotas_pagas_ano = session.query(Quota).filter(and_(Quota.paga == True, Quota.data_pagamento.startswith(str(ano_sel)))).all()
        if quotas_pagas_ano:
            df_fracoes = pd.DataFrame([{"Mês": q.data_pagamento[5:7], "Fração": f"Fr. {q.condomino.fracao}", "Valor Pago": q.valor} for q in quotas_pagas_ano])
            df_fracoes_grouped = df_fracoes.groupby(["Mês", "Fração"]).sum().reset_index()
            df_fracoes_grouped["Mês_Nome"] = df_fracoes_grouped["Mês"].map(meses_map)
            
            fig3 = px.bar(df_fracoes_grouped, x="Mês_Nome", y="Valor Pago", color="Fração", barmode="stack", text_auto=".0f")
            fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text="Frações", margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
        else: st.info("Sem pagamentos registados.")

with tab_devedores:
    with st.container(border=True):
        st.subheader("⚠️ Dívidas ao Condomínio")
        todas_dividas = session.query(Quota).filter_by(paga=False).all()
        if todas_dividas:
            df_dividas = pd.DataFrame([{"Fração": d.condomino.fracao, "Proprietário": d.condomino.nome, "Quotas em Atraso": 1, "Valor Total": d.valor} for d in todas_dividas])
            df_top = df_dividas.groupby(["Fração", "Proprietário"]).sum().reset_index().sort_values(by="Valor Total", ascending=False)
            
            c_graf, c_tab = st.columns([1.5, 1])
            with c_graf:
                fig4 = px.bar(df_top.head(7), x="Valor Total", y="Fração", orientation="h", text_auto=".2f", color="Valor Total", color_continuous_scale="Reds")
                fig4.update_layout(yaxis={"categoryorder":"total ascending"}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})
            with c_tab:
                st.dataframe(df_top, hide_index=True, column_config={"Quotas em Atraso": st.column_config.NumberColumn("Nº Quotas", format="%d"), "Valor Total": st.column_config.NumberColumn("Em Dívida (€)", format="%.2f €")}, use_container_width=True)
        else:
            st.success("🎉 Excelente! Não existem condóminos com dívidas ativas.")