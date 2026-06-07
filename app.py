import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import base64
import smtplib
import unicodedata
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import date, datetime
from sqlalchemy import func, and_
from io import BytesIO

# Importações limpas (Sem a NotificacaoLida)
from models import Base, Condomino, Utilizador, Quota, Movimento, Ocorrencia, Orcamento, Documento, Fornecedor, Assembleia, Sondagem, VotoSondagem, Anuncio, Auditoria, Manutencao
from db import init_db, get_session, engine

# ==========================================
# VERIFICAÇÃO DE BIBLIOTECAS
# ==========================================
try:
    from werkzeug.security import generate_password_hash, check_password_hash
    WERKZEUG_INSTALLED = True
except ImportError:
    WERKZEUG_INSTALLED = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_INSTALLED = True
except ImportError:
    REPORTLAB_INSTALLED = False

# ==========================================
# CLASSE DE PAGINAÇÃO DINÂMICA PREMIUM (REPORTLAB)
# ==========================================
if REPORTLAB_INSTALLED:
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_number(num_pages)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def draw_page_number(self, page_count):
            self.saveState()
            self.setFont("Helvetica", 9)
            self.setFillColor(colors.HexColor("#64748b"))
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(50, 45, 545, 45)
            texto_pagina = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(545, 30, texto_pagina)
            self.drawString(50, 30, " A3® Portal do Condomínio")
            self.restoreState()

# ==========================================
# 1. GESTÃO DE CONFIGURAÇÕES (JSON) E HELPERS
# ==========================================
CONFIG_FILE = "config.json"

def carregar_configs():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "NOME_CONDOMINIO": "Condomínio Praceta Antero de Quental, Nº 5",
        "MORADA_CONDOMINIO": "2950-562 Quinta do Anjo",
        "NIF_CONDOMINIO": "901571253",
        "IBAN_CONDOMINIO": "PT50 0018 000801049161020 73",
        "VALOR_MENSAL_FIXO": 50.00,
        "AVISO_ATIVO": False,
        "AVISO_GLOBAL": ""
    }

def guardar_configs(configs):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(configs, f, indent=4, ensure_ascii=False)

config = carregar_configs()

def formatar_username(nome_completo):
    partes = nome_completo.strip().split()
    if len(partes) > 1: raw_user = f"{partes[0][0]}{partes[-1]}"
    else: raw_user = partes[0]
    raw_user = raw_user.lower()
    return "".join(c for c in unicodedata.normalize("NFD", raw_user) if unicodedata.category(c) != "Mn")

# ==========================================
# 2. CONFIGURAÇÕES GLOBAIS E BASE DE DADOS
# ==========================================
init_db()
session = get_session()

def registar_log(sessao_db, acao, detalhes=""):
    user = st.session_state.get("username", "Sistema")
    novo_log = Auditoria(username=user, acao=acao, detalhes=detalhes)
    sessao_db.add(novo_log)

st.set_page_config(page_title="A3® Portal do Condomínio", page_icon="🏢", layout="wide")
caminho_logo = "logo.png"

# ==========================================
# INICIALIZAÇÃO DE SEGURANÇA E ESTADOS
# ==========================================
if WERKZEUG_INSTALLED:
    admin_existe = session.query(Utilizador).filter_by(username="admin").first()
    if not admin_existe:
        admin_user = Utilizador(
            username="admin", password_hash=generate_password_hash("M4ralisa1979#"), perfil="Admin", modo_leitura=False, perm_download_docs=True,
            perm_dashboard=True, perm_condominos=True, perm_quotas=True, perm_financas=True, perm_recibos=True, perm_assembleias=True, perm_arquivo=True, perm_fornecedores=True, perm_ocorrencias=True, perm_mural=True
        )
        session.add(admin_user)
        registar_log(session, "SISTEMA", "Criação automática do utilizador administrador padrão.")
        session.commit()

if "logado" not in st.session_state: st.session_state.logado = False
if "username" not in st.session_state: st.session_state.username = None
if "perfil" not in st.session_state: st.session_state.perfil = None
if "condomino_id" not in st.session_state: st.session_state.condomino_id = None
if "user_id" not in st.session_state: st.session_state.user_id = None

# Memória da sessão para as Notificações
if "alertas_lidos" not in st.session_state: st.session_state.alertas_lidos = []

if "perm_dashboard" not in st.session_state: st.session_state.perm_dashboard = False
if "perm_condominos" not in st.session_state: st.session_state.perm_condominos = False
if "perm_quotas" not in st.session_state: st.session_state.perm_quotas = False
if "perm_financas" not in st.session_state: st.session_state.perm_financas = False
if "perm_recibos" not in st.session_state: st.session_state.perm_recibos = False
if "perm_assembleias" not in st.session_state: st.session_state.perm_assembleias = False
if "perm_arquivo" not in st.session_state: st.session_state.perm_arquivo = False
if "perm_fornecedores" not in st.session_state: st.session_state.perm_fornecedores = False
if "perm_ocorrencias" not in st.session_state: st.session_state.perm_ocorrencias = False
if "perm_mural" not in st.session_state: st.session_state.perm_mural = True
if "modo_leitura" not in st.session_state: st.session_state.modo_leitura = False
if "perm_download_docs" not in st.session_state: st.session_state.perm_download_docs = True

if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "edit_type" not in st.session_state: st.session_state.edit_type = None
if "form_key" not in st.session_state: st.session_state.form_key = 0

def clear_edit():
    st.session_state.edit_id = None; st.session_state.edit_type = None; st.session_state.form_key += 1 

if "toast" in st.session_state:
    st.toast(st.session_state.toast[0], icon=st.session_state.toast[1])
    del st.session_state.toast

@st.cache_data
def convert_df(df): return df.to_csv(index=False, sep=";").encode("utf-8")

def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as img_file: return base64.b64encode(img_file.read()).decode()
    return ""

def enviar_email_real(destinatario, assunto, corpo, anexo_bytes=None, nome_anexo="documento.pdf"):
    try: email_user, email_pass = st.secrets["EMAIL_USER"], st.secrets["EMAIL_PASS"]
    except Exception: email_user, email_pass = config.get("EMAIL_USER", ""), config.get("EMAIL_PASS", "")
    
    if not email_user or not email_pass:
        st.error("⚠️ Credenciais de email não configuradas."); return False
        
    try:
        msg = MIMEMultipart()
        msg["From"], msg["To"], msg["Subject"] = email_user, destinatario, assunto
        msg.attach(MIMEText(corpo, "plain", "utf-8")) 
        if anexo_bytes:
            part = MIMEApplication(anexo_bytes, Name=nome_anexo)
            part["Content-Disposition"] = f'attachment; filename="{nome_anexo}"'
            msg.attach(part)
        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(email_user, email_pass)
        server.sendmail(email_user, destinatario, msg.as_string()); server.quit(); return True
    except Exception as e:
        st.error(f"Erro técnico no envio de email: {e}"); return False

# ==========================================
# CSS E LAYOUT GLOBAL
# ==========================================
st.markdown("""
<style>
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e2e8f0; padding: 5% 5% 5% 10%; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; background-color: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; padding: 8px; }
    div[data-testid="stAlert"] { border-radius: 8px; }
    @keyframes piscar { 0% { opacity: 1; transform: scale(1); color: #fbbf24; } 50% { opacity: 0.5; transform: scale(1.1); color: #f59e0b; } 100% { opacity: 1; transform: scale(1); color: #fbbf24; } }
    .notificacao-ativa { display: inline-block; animation: piscar 1.5s infinite ease-in-out; font-size: 1.2em; margin-right: 5px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# PÁGINA E MOTOR DE NOTIFICAÇÕES (Em Memória)
# ==========================================
hoje = date.today()
meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

def verificar_notificacoes_pendentes(sessao_db, perfil, condomino_id):
    """Verifica notificações ativas puxando os ocultos da sessão de memória do Streamlit"""
    from datetime import datetime, date
    hoje_local = date.today()
    lidos = st.session_state.get("alertas_lidos", [])
    
    ass_futuras = sessao_db.query(Assembleia).filter_by(realizada=False).all()
    for a in ass_futuras:
        if f"ass_{a.id}" not in lidos:
            try:
                d_ass = datetime.strptime(a.data_agendada, "%Y-%m-%d").date()
                if (d_ass - hoje_local).days <= 5: return True
            except Exception: pass

    if perfil == "Admin":
        for o in sessao_db.query(Ocorrencia).filter_by(resolvida=False).all():
            if f"oc_{o.id}" not in lidos: return True
        for m in sessao_db.query(Manutencao).filter_by(estado="Pendente").all():
            if f"man_{m.id}" not in lidos: return True

    if condomino_id:
        for d in sessao_db.query(Quota).filter_by(condomino_id=condomino_id, paga=False).all():
            if f"quota_{d.id}" not in lidos: return True
        for s in sessao_db.query(Sondagem).filter_by(ativa=True).all():
            if not sessao_db.query(VotoSondagem).filter_by(sondagem_id=s.id, condomino_id=condomino_id).first():
                if f"sond_{s.id}" not in lidos: return True
    return False

# PÁGINA CENTRAL DE NOTIFICAÇÕES
def pagina_notificacoes():
    from datetime import datetime
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/notifications_active: Central de Notificações")
    st.write("Acompanhe aqui as pendências ativas. Pode ocultar os avisos temporariamente (reaparecem ao entrar novamente) ou resolver o assunto para desaparecer de vez.")
    
    alertas_encontrados = False
    lidos = st.session_state.get("alertas_lidos", [])

    if st.session_state.perfil == "Admin":
        st.subheader("🛠️ Operações Pendentes da Administração")
        ocs = session.query(Ocorrencia).filter_by(resolvida=False).all()
        for o in ocs:
            uid = f"oc_{o.id}"
            if uid not in lidos:
                alertas_encontrados = True
                col_al, col_bt = st.columns([5, 1])
                col_al.error(f"**Avaria por Resolver:** '{o.titulo}' (Reportado por {o.criado_por}).", icon="🚨")
                if col_bt.button("❌ Ocultar", key=f"h_{uid}", use_container_width=True):
                    st.session_state.alertas_lidos.append(uid); st.rerun()
                        
        mans = session.query(Manutencao).filter_by(estado="Pendente").all()
        for m in mans:
            uid = f"man_{m.id}"
            if uid not in lidos:
                alertas_encontrados = True
                col_al, col_bt = st.columns([5, 1])
                col_al.warning(f"**Manutenção:** '{m.descricao}' em {m.equipamento} agendada para {m.data_planeada}.", icon="⚙️")
                if col_bt.button("❌ Ocultar", key=f"h_{uid}", use_container_width=True):
                    st.session_state.alertas_lidos.append(uid); st.rerun()

    st.subheader("👤 Os Meus Alertas")
    ass_futuras = session.query(Assembleia).filter_by(realizada=False).all()
    for a in ass_futuras:
        uid = f"ass_{a.id}"
        if uid not in lidos:
            try:
                d_ass = datetime.strptime(a.data_agendada, "%Y-%m-%d").date()
                dias_restantes = (d_ass - hoje).days
                if 0 <= dias_restantes <= 5:
                    alertas_encontrados = True
                    col_al, col_bt = st.columns([5, 1])
                    col_al.info(f"**Assembleia Próxima:** '{a.titulo}' decorre em {dias_restantes} dia(s).", icon="📅")
                    if col_bt.button("❌ Ocultar", key=f"h_{uid}", use_container_width=True):
                        st.session_state.alertas_lidos.append(uid); st.rerun()
                elif dias_restantes < 0:
                    alertas_encontrados = True
                    col_al, col_bt = st.columns([5, 1])
                    col_al.error(f"**Atraso:** A assembleia '{a.titulo}' de {a.data_agendada} ainda não foi fechada.", icon="⚠️")
                    if col_bt.button("❌ Ocultar", key=f"h_{uid}", use_container_width=True):
                        st.session_state.alertas_lidos.append(uid); st.rerun()
            except Exception: pass

    if st.session_state.condomino_id:
        dividas = session.query(Quota).filter_by(condomino_id=st.session_state.condomino_id, paga=False).all()
        for d in dividas:
            uid = f"quota_{d.id}"
            if uid not in lidos:
                alertas_encontrados = True
                col_al, col_bt = st.columns([5, 1])
                col_al.error(f"**Tesouraria:** Quota de **{d.mes_ano}** ({d.valor:.2f} €) a pagamento.", icon="💰")
                if col_bt.button("❌ Ocultar", key=f"h_{uid}", use_container_width=True):
                    st.session_state.alertas_lidos.append(uid); st.rerun()
                        
        sond_ativas = session.query(Sondagem).filter_by(ativa=True).all()
        for s in sond_ativas:
            uid = f"sond_{s.id}"
            if uid not in lidos:
                if not session.query(VotoSondagem).filter_by(sondagem_id=s.id, condomino_id=st.session_state.condomino_id).first():
                    alertas_encontrados = True
                    col_al, col_bt = st.columns([5, 1])
                    col_al.info(f"**Votação em Curso:** Sondagem pendente sobre '{s.pergunta}'.", icon="🗳️")
                    if col_bt.button("❌ Ocultar", key=f"h_{uid}", use_container_width=True):
                        st.session_state.alertas_lidos.append(uid); st.rerun()

    if not alertas_encontrados:
        st.success("🎉 Tudo verificado e em dia! Sem pendências ativas.")

PAGE_NOTIFICACOES = st.Page(pagina_notificacoes, title="Central de Notificações", icon=":material/notifications_active:")

def configurar_sidebar():
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if os.path.exists("logo.png"):
        col1, col2, col3 = st.sidebar.columns([1, 2.5, 1])
        with col2: st.image("logo.png", width="stretch")
    st.sidebar.title(":material/corporate_fare: A3® Cond.Gest")
    st.sidebar.markdown("---")
    
    if st.session_state.logado:
        st.sidebar.write(f":material/account_circle: Olá, **{st.session_state.username}**")
        if st.session_state.modo_leitura: st.sidebar.caption(":material/visibility: MODO LEITURA")
            
        tem_alertas = verificar_notificacoes_pendentes(session, st.session_state.perfil, st.session_state.condomino_id)
        if tem_alertas:
            html_lampada = '<span class="notificacao-ativa">💡</span>'
            st.sidebar.markdown(f"{html_lampada} **Tens notificações pendentes!**", unsafe_allow_html=True)
            if st.sidebar.button("Ir para Central de Notificações", use_container_width=True, type="primary"):
                st.switch_page(PAGE_NOTIFICACOES) 
        else:
            st.sidebar.markdown("🔕 *Sem notificações novas.*")
        st.sidebar.markdown("---")

        if st.sidebar.button(":material/logout: Terminar Sessão", width="stretch"):
            st.session_state.logado = False
            st.session_state.username = None; st.session_state.perfil = None; st.session_state.condomino_id = None; st.session_state.user_id = None; st.session_state.modo_leitura = False
            st.session_state.alertas_lidos = []
            st.rerun()
        st.sidebar.markdown("---")

    st.sidebar.subheader(":material/schedule: Filtros de Tempo")
    mes_sel = st.sidebar.selectbox("Mês de Trabalho", meses, index=hoje.month - 1)
    ano_sel = st.sidebar.number_input("Ano de Trabalho", min_value=2020, value=hoje.year)
    idx_mes = meses.index(mes_sel) + 1
    str_inicio = f"{ano_sel}-{idx_mes:02d}-01"
    str_fim = f"{ano_sel if idx_mes < 12 else ano_sel+1}-{idx_mes+1 if idx_mes < 12 else 1:02d}-01"
    mes_str = f"{idx_mes:02d}/{ano_sel}" 
    st.sidebar.markdown("---")
    
    return mes_sel, ano_sel, str_inicio, str_fim, mes_str

# ==========================================
# RESTANTES PÁGINAS DO SISTEMA
# ==========================================
def pagina_login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.2, 1.2, 1.2]) 
    with c2:
        with st.container(border=True):
            if os.path.exists("logo.png"):
                col_esp, col_img, col_esp2 = st.columns([1, 1.5, 1])
                with col_img: st.image("logo.png", use_container_width=True)
            st.markdown("<div style='text-align: center;'><h2 style='margin-bottom: 0px; color: #1e293b;'>A3® Portal do Condomínio</h2></div>", unsafe_allow_html=True)
            with st.form("form_login", clear_on_submit=True):
                user = st.text_input("👤 Nome de Utilizador")
                pwd = st.text_input("🔒 Password", type="password")
                submit = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)
                if submit:
                    utilizador_db = session.query(Utilizador).filter_by(username=user.lower()).first()
                    if utilizador_db and check_password_hash(utilizador_db.password_hash, pwd):
                        st.session_state.logado = True; st.session_state.user_id = utilizador_db.id; st.session_state.username = utilizador_db.username
                        st.session_state.perfil = utilizador_db.perfil; st.session_state.condomino_id = utilizador_db.condomino_id
                        st.session_state.perm_dashboard = utilizador_db.perm_dashboard; st.session_state.perm_condominos = utilizador_db.perm_condominos
                        st.session_state.perm_quotas = utilizador_db.perm_quotas; st.session_state.perm_financas = utilizador_db.perm_financas
                        st.session_state.perm_recibos = utilizador_db.perm_recibos; st.session_state.perm_assembleias = utilizador_db.perm_assembleias
                        st.session_state.perm_arquivo = utilizador_db.perm_arquivo; st.session_state.perm_fornecedores = utilizador_db.perm_fornecedores
                        st.session_state.perm_ocorrencias = utilizador_db.perm_ocor
