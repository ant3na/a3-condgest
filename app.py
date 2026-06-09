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
from datetime import datetime, date
from sqlalchemy import func, and_, or_
from io import BytesIO

# Importações limpas e completas dos nossos módulos refatorados
from models import Base, Condomino, Utilizador, Quota, Movimento, Ocorrencia, Orcamento, Documento, Fornecedor, Assembleia, Sondagem, VotoSondagem, Anuncio, Auditoria, Contrato, Intervencao
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
        "TITULO_LOGIN": "A3® Portal do Condomínio",
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
    if len(partes) > 1:
        raw_user = f"{partes[0][0]}{partes[-1]}"
    else:
        raw_user = partes[0]
    raw_user = raw_user.lower()
    return "".join(c for c in unicodedata.normalize("NFD", raw_user) if unicodedata.category(c) != "Mn")

# ==========================================
# 2. CONFIGURAÇÕES GLOBAIS E BASE DE DADOS
# ==========================================
init_db()
session = get_session()

st.set_page_config(page_title="A3® Portal do Condomínio", page_icon="🏢", layout="wide")

caminho_logo = "logo.png"

# ==========================================
# INICIALIZAÇÃO DE SEGURANÇA E ESTADOS
# ==========================================
if WERKZEUG_INSTALLED:
    admin_existe = session.query(Utilizador).filter_by(username="admin").first()
    if not admin_existe:
        admin_user = Utilizador(
            username="admin", 
            password_hash=generate_password_hash("M4ralisa1979#"), 
            perfil="Admin",
            modo_leitura=False,
            perm_download_docs=True,
            perm_dashboard=True, perm_condominos=True, perm_quotas=True, perm_financas=True, 
            perm_recibos=True, perm_assembleias=True, perm_arquivo=True, perm_fornecedores=True, perm_ocorrencias=True,
            perm_mural=True
        )
        session.add(admin_user)
        session.commit()

if "logado" not in st.session_state: st.session_state.logado = False
if "username" not in st.session_state: st.session_state.username = None
if "perfil" not in st.session_state: st.session_state.perfil = None
if "condomino_id" not in st.session_state: st.session_state.condomino_id = None
if "user_id" not in st.session_state: st.session_state.user_id = None

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
    st.session_state.edit_id = None
    st.session_state.edit_type = None
    st.session_state.form_key += 1 

if "toast" in st.session_state:
    st.toast(st.session_state.toast[0], icon=st.session_state.toast[1])
    del st.session_state.toast

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False, sep=";").encode("utf-8")

def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

# ==========================================
# FUNÇÃO CORE DE AUDITORIA ROTATIVA (MÁX 200 LOGS)
# ==========================================
def registar_auditoria(acao, entidade, detalhes):
    if st.session_state.logado and st.session_state.username:
        try:
            novo_log = Auditoria(
                data_hora=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                username=st.session_state.username,
                acao=acao,
                entidade=entidade,
                detalhes=detalhes
            )
            session.add(novo_log)
            session.commit()
            
            total_logs = session.query(Auditoria).count()
            if total_logs > 200:
                logs_a_remover = session.query(Auditoria).order_by(Auditoria.id.asc()).limit(total_logs - 200).all()
                for log_antigo in logs_a_remover:
                    session.delete(log_antigo)
                session.commit()
        except Exception as e:
            session.rollback()
            st.error(f"Erro ao processar auditoria do sistema: {e}")

# ==========================================
# FUNÇÕES CORE (EMAILS E PDFs)
# ==========================================
def enviar_email_real(destinatario, assunto, corpo, anexo_bytes=None, nome_anexo="documento.pdf"):
    try:
        email_user = st.secrets["EMAIL_USER"]
        email_pass = st.secrets["EMAIL_PASS"]
    except Exception:
        email_user = config.get("EMAIL_USER", "")
        email_pass = config.get("EMAIL_PASS", "")
    
    if not email_user or not email_pass:
        st.error("⚠️ Credenciais de email não configuradas.")
        return False
        
    try:
        msg = MIMEMultipart()
        msg["From"] = email_user
        msg["To"] = destinatario
        msg["Subject"] = assunto
        msg.attach(MIMEText(corpo, "plain", "utf-8")) 
        
        if anexo_bytes:
            part = MIMEApplication(anexo_bytes, Name=nome_anexo)
            part["Content-Disposition"] = f'attachment; filename="{nome_anexo}"'
            msg.attach(part)
            
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(email_user, email_pass)
        server.sendmail(email_user, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erro técnico no envio de email: {e}")
        return False

def desenhar_cabecalho_pdf(canvas_obj, doc, titulo, subtitulo):
    width, height = A4
    offset_y = 20
    y_esq = height - 60 - offset_y
    
    if os.path.exists(caminho_logo):
        try:
            canvas_obj.drawImage(caminho_logo, 50, height - 110 - offset_y, width=80, height=80, preserveAspectRatio=True, mask="auto")
            y_esq = height - 135 - offset_y
        except Exception: pass 

    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawString(50, y_esq, config.get("NOME_CONDOMINIO", ""))
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawString(50, y_esq - 15, config.get("MORADA_CONDOMINIO", ""))
    canvas_obj.drawString(50, y_esq - 30, f"NIF: {config.get('NIF_CONDOMINIO', '')}")
    canvas_obj.drawString(50, y_esq - 45, f"IBAN: {config.get('IBAN_CONDOMINIO', '')}")

    canvas_obj.setFont("Helvetica-Bold", 20)
    canvas_obj.drawRightString(width - 50, height - 60 - offset_y, titulo)
    canvas_obj.setFont("Helvetica", 12)
    canvas_obj.drawRightString(width - 50, height - 80 - offset_y, subtitulo)

    y_linha = y_esq - 65
    canvas_obj.setStrokeColorRGB(0.8, 0.8, 0.8)
    canvas_obj.line(50, y_linha, width - 50, y_linha)

def gerar_pdf_recibo(q):
    if not REPORTLAB_INSTALLED: return None
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    periodo_seguro = q.mes_ano.replace("/", "-")
    titulo_pdf = f"Recibo_{q.condomino.nome.replace(' ', '_')}_{q.condomino.fracao}_{periodo_seguro}"
    c.setTitle(titulo_pdf)

    desenhar_cabecalho_pdf(c, None, "RECIBO", f"Nº Fatura/Recibo: {q.id:05d}")

    width, height = A4
    meio_pagina = height / 2.0
    y_base = height - 265
    
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 50, height - 115, f"Data: {q.data_pagamento}")

    y_cond = y_base
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(50, y_cond, "DADOS DO CONDÓMINO:")

    y_cond_val = y_cond - 20
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 11)
    c.drawString(50, y_cond_val, f"Nome: {q.condomino.nome}")
    c.drawString(50, y_cond_val - 15, f"Fração: {q.condomino.fracao}")

    nif_str = q.condomino.nif if q.condomino.nif else "N/A"
    c.drawString(300, y_cond_val, f"NIF: {nif_str}")
    c.drawString(300, y_cond_val - 15, f"Permilagem: {q.condomino.permilagem:.2f} ‰")

    y_caixa_topo = y_cond_val - 45
    c.setStrokeColorRGB(0.15, 0.65, 0.27)
    c.setLineWidth(4)
    c.line(50, y_caixa_topo - 40, 50, y_caixa_topo) 
    c.setLineWidth(1)
    c.setFillColorRGB(0.97, 0.97, 0.97) 
    c.rect(52, y_caixa_topo - 40, width - 102, 40, stroke=0, fill=1)

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 11)
    texto1 = f"Declaramos que recebemos a quantia de {q.valor:.2f} Euros,"
    texto2 = f"referente ao pagamento da quota de condomínio do período de {q.mes_ano}."
    c.drawString(65, y_caixa_topo - 15, texto1)
    c.drawString(65, y_caixa_topo - 30, texto2)

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(width / 2.0, meio_pagina + 30, "Documento processado por computador e sem obrigatoriedade de assinatura.")

    c.setLineWidth(1)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setDash(4, 4) 
    c.line(0, meio_pagina, width, meio_pagina)
    
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.7, 0.7, 0.7)
    c.drawString(30, meio_pagina + 5, "✂ - - - Cortar aqui - - -")

    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def obter_estilo_tabela_premium():
    return TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e293b")), 
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 9),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("ALIGN", (-1,0), (-1,-1), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LINEBELOW", (0,0), (-1,0), 1, colors.HexColor("#0f172a")),
        ("LINEBELOW", (0,1), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,1), (-1,-1), 9),
        ("TEXTCOLOR", (0,1), (-1,-1), colors.HexColor("#334155")),
    ])

def gerar_pdf_extrato(df, mes, ano, saldo_anterior):
    if not REPORTLAB_INSTALLED: return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=230, bottomMargin=60)
    
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"].clone("style_normal")
    style_normal.fontName = "Helvetica"
    style_normal.fontSize = 10
    style_normal.spaceAfter = 6
    
    style_heading = styles["Heading2"].clone("style_heading")
    style_heading.fontName = "Helvetica-Bold"
    style_heading.fontSize = 11
    style_heading.spaceAfter = 10
    style_heading.spaceBefore = 15
    
    elements = []

    elements.append(Paragraph(f"<b>1. DETALHE DE MOVIMENTOS</b>", style_heading))
    tabela_data = [["Data", "Tipo", "Descrição", "Valor (EUR)"]]
    for _, row in df.iterrows():
        tabela_data.append([str(row["Data"]), str(row["Tipo"]), str(row["Descrição"]), f"{row['Valor']:.2f}"])

    t = Table(tabela_data, colWidths=[70, 90, 250, 80])
    t.setStyle(obter_estilo_tabela_premium())
    elements.append(t)
    elements.append(Spacer(1, 15))

    total_rec = df[df["Tipo"].str.contains("Receita", na=False)]["Valor"].sum()
    total_desp = df[df["Tipo"].str.contains("Despesa", na=False)]["Valor"].sum()
    saldo_final = saldo_anterior + total_rec - total_desp

    elements.append(Paragraph(f"<b>2. RESUMO FINANCEIRO DO MÊS</b>", style_heading))
    elements.append(Paragraph(f"<b>Saldo Transitado Anterior:</b> {saldo_anterior:.2f} EUR", style_normal))
    elements.append(Paragraph(f"<b>(+) Entradas no Mês:</b> {total_rec:.2f} EUR", style_normal))
    elements.append(Paragraph(f"<b>(-) Saídas no Mês:</b> {total_desp:.2f} EUR", style_normal))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f"<b>(=) SALDO FINAL DO MÊS:</b> <b>{saldo_final:.2f} EUR</b>", style_normal))

    def cabecalho_extrato(canvas_obj, doc_obj):
        desenhar_cabecalho_pdf(canvas_obj, doc_obj, "EXTRATO MENSAL", f"Período: {mes} {ano}")

    doc.build(elements, onFirstPage=cabecalho_extrato, onLaterPages=cabecalho_extrato, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def gerar_pdf_relatorio_anual(ano, saldo_anterior, total_quotas, total_receitas, total_despesas, df_despesas_agrupadas):
    if not REPORTLAB_INSTALLED: return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=230, bottomMargin=60)
    
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"].clone("style_normal")
    style_normal.fontName = "Helvetica"
    style_normal.fontSize = 10
    style_normal.spaceAfter = 6
    
    style_heading = styles["Heading2"].clone("style_heading")
    style_heading.fontName = "Helvetica-Bold"
    style_heading.fontSize = 11
    style_heading.spaceAfter = 10
    style_heading.spaceBefore = 15

    elements = []
    
    elements.append(Paragraph(f"<b>1. DETALHAMENTO DE DESPESAS (Por Categoria)</b>", style_heading))
    
    if not df_despesas_agrupadas.empty:
        tabela_data = [["Descrição / Categoria", "Valor Total Gasto (EUR)"]]
        for _, row in df_despesas_agrupadas.iterrows():
            tabela_data.append([str(row["Descrição"]), f"{row['Valor']:.2f}"])
        
        t = Table(tabela_data, colWidths=[350, 140])
        t.setStyle(obter_estilo_tabela_premium())
        elements.append(t)
    else:
        elements.append(Paragraph("Não existem despesas registadas neste ano civil.", style_normal))

    elements.append(Spacer(1, 15))

    saldo_final = saldo_anterior + total_quotas + total_receitas - total_despesas
    elements.append(Paragraph(f"<b>2. RESUMO FINANCEIRO GLOBAL</b>", style_heading))
    elements.append(Paragraph(f"<b>Saldo Transitado do Ano Anterior:</b> {saldo_anterior:.2f} EUR", style_normal))
    elements.append(Paragraph(f"<b>(+) Total de Quotas Cobradas:</b> {total_quotas:.2f} EUR", style_normal))
    elements.append(Paragraph(f"<b>(+) Outras Receitas:</b> {total_receitas:.2f} EUR", style_normal))
    elements.append(Paragraph(f"<b>(-) Total de Despesas:</b> {total_despesas:.2f} EUR", style_normal))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f"<b>(=) SALDO FINAL DO ANO:</b> <b>{saldo_final:.2f} EUR</b>", style_normal))

    def cabecalho_anual(canvas_obj, doc_obj):
        desenhar_cabecalho_pdf(canvas_obj, doc_obj, "RELATÓRIO ANUAL", f"Fecho de Contas: {ano}")

    doc.build(elements, onFirstPage=cabecalho_anual, onLaterPages=cabecalho_anual, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def gerar_pdf_ata(a):
    if not REPORTLAB_INSTALLED: return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=230, bottomMargin=60)
    
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"].clone("style_normal")
    style_normal.fontName = "Helvetica"
    style_normal.fontSize = 10
    style_normal.spaceAfter = 10
    style_normal.alignment = 4 
    
    style_heading = styles["Heading2"].clone("style_heading")
    style_heading.fontName = "Helvetica-Bold"
    style_heading.fontSize = 11
    style_heading.spaceAfter = 15
    
    elements = []
    
    elements.append(Paragraph(f"<b>{a.titulo}</b>", style_heading))
    elements.append(Paragraph(f"<b>Data de Realização:</b> {a.data_agendada}", style_normal))
    elements.append(Spacer(1, 15))
    
    if a.texto_ata:
        for p in a.texto_ata.split("\n"):
            if p.strip():
                elements.append(Paragraph(p.strip().replace("\n", "<br/>"), style_normal))
                
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("<i>Ata redigida e processada informaticamente pelo sistema A3® Portal do Condomínio.</i>", style_normal))

    def cabecalho_ata(canvas_obj, doc_obj):
        desenhar_cabecalho_pdf(canvas_obj, doc_obj, "ATA DE ASSEMBLEIA", f"Ref: ATA-{a.id:04d}")

    doc.build(elements, onFirstPage=cabecalho_ata, onLaterPages=cabecalho_ata, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# ==========================================
# CSS E LAYOUT GLOBAL
# ==========================================
st.markdown("""
<style>
    /* Estilização dos Cartões de Métrica */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        border-color: #cbd5e1;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"] { 
        border-radius: 12px; 
        background-color: #ffffff; 
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); 
        border: 1px solid #e2e8f0; 
        padding: 8px; 
    }
    
    /* Afinar os cantos dos alertas (sucessos, erros, infos) */
    div[data-testid="stAlert"] { 
        border-radius: 10px; 
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# BARRA LATERAL (LOGO E FILTROS)
# ==========================================
hoje = date.today()
meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

def configurar_sidebar():
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if os.path.exists("logo.png"):
        col1, col2, col3 = st.sidebar.columns([1, 2.5, 1])
        with col2: st.image("logo.png", width="stretch")
    st.sidebar.title(":material/corporate_fare: A3® Cond.Gest")
    st.sidebar.markdown("---")
    
    if st.session_state.logado:
        st.sidebar.write(f":material/account_circle: Olá, **{st.session_state.username}**")
        if st.session_state.modo_leitura:
            st.sidebar.caption(":material/visibility: MODO LEITURA")
        
        if st.sidebar.button(":material/logout: Terminar Sessão", width="stretch"):
            st.session_state.logado = False
            st.session_state.username = None
            st.session_state.perfil = None
            st.session_state.condomino_id = None
            st.session_state.user_id = None
            st.session_state.modo_leitura = False
            st.rerun()
        st.sidebar.markdown("---")

    st.sidebar.subheader(":material/schedule: Filtros de Tempo")
    
    # --- INOVAÇÃO: AÇÕES RÁPIDAS (Quick Presets) ---
    # Inicializa os valores padrão na memória da sessão na primeira visita
    if "filtro_mes" not in st.session_state:
        st.session_state.filtro_mes = meses[hoje.month - 1]
    if "filtro_ano" not in st.session_state:
        st.session_state.filtro_ano = hoje.year

    # Criar a barra de navegação rápida (3 colunas compactas)
    c_ant, c_hoje, c_seg = st.sidebar.columns([1, 1.2, 1])
    
    if c_ant.button("◀ Mês", use_container_width=True, help="Retroceder para o mês anterior"):
        idx = meses.index(st.session_state.filtro_mes)
        if idx == 0:
            st.session_state.filtro_mes = meses[11]
            st.session_state.filtro_ano -= 1
        else:
            st.session_state.filtro_mes = meses[idx - 1]
        st.rerun()
        
    if c_hoje.button("📅 Atual", use_container_width=True, help="Saltar rapidamente para o mês de hoje"):
        st.session_state.filtro_mes = meses[hoje.month - 1]
        st.session_state.filtro_ano = hoje.year
        st.rerun()
        
    if c_seg.button("Mês ▶", use_container_width=True, help="Avançar para o mês seguinte"):
        idx = meses.index(st.session_state.filtro_mes)
        if idx == 11:
            st.session_state.filtro_mes = meses[0]
            st.session_state.filtro_ano += 1
        else:
            st.session_state.filtro_mes = meses[idx + 1]
        st.rerun()

    # Os campos agora estão amarrados à memória da sessão usando a propriedade 'key'
    mes_sel = st.sidebar.selectbox("Mês de Trabalho", meses, key="filtro_mes")
    ano_sel = st.sidebar.number_input("Ano de Trabalho", min_value=2020, key="filtro_ano")
    
    idx_mes = meses.index(mes_sel) + 1
    str_inicio = f"{ano_sel}-{idx_mes:02d}-01"
    str_fim = f"{ano_sel if idx_mes < 12 else ano_sel+1}-{idx_mes+1 if idx_mes < 12 else 1:02d}-01"
    mes_str = f"{idx_mes:02d}/{ano_sel}" 
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 **Dica:** Altere entre o Modo Claro e Escuro clicando nos **⋮** no canto superior direito > **Settings** > **Theme**.")
    
    return mes_sel, ano_sel, str_inicio, str_fim, mes_str
# ==========================================
# MÓDULOS DE PÁGINAS
# ==========================================
def pagina_login():
    has_bg = os.path.exists("bg_login.png")
    titulo_login = config.get("TITULO_LOGIN", "A3® Portal do Condomínio")

    # --- CSS DINÂMICO E EXCLUSIVO DA PÁGINA DE LOGIN ---
    if has_bg:
        bg_base64 = get_image_base64("bg_login.png")
        st.markdown(f"""
        <style>
            [data-testid="stHeader"] {{
                display: none;
            }}
            /* Imagem de fundo em ecrã total */
            .stApp {{
                background-image: url("data:image/png;base64,{bg_base64}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
            .block-container {{
                padding-top: 2rem !important;
                padding-bottom: 0rem !important;
            }}
            
            /* =========================================================
               MELHORIAS DE CORES QUANDO A IMAGEM DE FUNDO ESTÁ ATIVA
               ========================================================= */
            /* 1. Forçar a caixa de login a ser branca sólida para total isolamento da foto */
            div[data-testid="stVerticalBlockBorderWrapper"] {{
                background-color: #ffffff !important;
                border: 1px solid #e2e8f0 !important;
                border-radius: 16px !important;
                padding: 20px !important;
                box-shadow: 0px 15px 45px rgba(0, 0, 0, 0.6) !important;
            }}
            
            /* 2. Forçar coerência total nas letras internas (Escuras e Legíveis) */
            div[data-testid="stVerticalBlockBorderWrapper"] h3,
            div[data-testid="stVerticalBlockBorderWrapper"] p,
            div[data-testid="stVerticalBlockBorderWrapper"] label,
            div[data-testid="stVerticalBlockBorderWrapper"] span,
            div[data-testid="stVerticalBlockBorderWrapper"] details summary {{
                color: #0f172a !important;
                font-weight: 500 !important;
                text-shadow: none !important;
            }}
            
            /* 3. Dar destaque absoluto aos campos de input para sobressaírem na caixa */
            div[data-testid="stVerticalBlockBorderWrapper"] input {{
                background-color: #f1f5f9 !important; /* Fundo cinza claro contrastante */
                color: #0f172a !important; /* Texto digitado escuro */
                border: 1px solid #cbd5e1 !important; /* Borda bem definida */
                border-radius: 8px !important;
                padding: 10px !important;
            }}
            
            /* Ajuste de cor do texto informativo do expander */
            div[data-testid="stVerticalBlockBorderWrapper"] .stAlert p {{
                color: #1e3a8a !important;
            }}
        </style>
        """, unsafe_allow_html=True)
    else:
        # CSS para o modo minimalista simples (Exatamente como estava, intocado!)
        st.markdown("""
        <style>
            [data-testid="stHeader"] {
                display: none;
            }
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 0rem !important;
            }
        </style>
        """, unsafe_allow_html=True)

    # Subfunção interna para renderizar o formulário de login
    def render_formulario_core():
        with st.container(border=True):
            if os.path.exists("logo.png"):
                col_esp, col_img, col_esp2 = st.columns([1, 1.5, 1])
                with col_img: st.image("logo.png", use_container_width=True)
            
            st.markdown("""
            <div style='text-align: center; margin-top: 5px;'>
                <h3 style='margin-bottom: 0px;'>Acesso Reservado</h3>
                <p style='font-size: 14px; margin-top: 5px; margin-bottom: 20px;'>Introduza as suas credenciais</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("form_login", clear_on_submit=True):
                user = st.text_input("👤 Nome de Utilizador", placeholder="Ex: jsilva")
                pwd = st.text_input("🔒 Password", type="password", placeholder="••••••••")
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("Entrar no Portal", type="primary", use_container_width=True)
                
                if submit:
                    if not user or not pwd:
                        st.warning("⚠️ Preencha os dois campos para entrar.")
                    else:
                        utilizador_db = session.query(Utilizador).filter_by(username=user.lower()).first()
                        if utilizador_db and check_password_hash(utilizador_db.password_hash, pwd):
                            st.session_state.logado = True
                            st.session_state.user_id = utilizador_db.id
                            st.session_state.username = utilizador_db.username
                            st.session_state.perfil = utilizador_db.perfil
                            st.session_state.condomino_id = utilizador_db.condomino_id
                            
                            st.session_state.perm_dashboard = utilizador_db.perm_dashboard
                            st.session_state.perm_condominos = utilizador_db.perm_condominos
                            st.session_state.perm_quotas = utilizador_db.perm_quotas
                            st.session_state.perm_financas = utilizador_db.perm_financas
                            st.session_state.perm_recibos = utilizador_db.perm_recibos
                            st.session_state.perm_assembleias = utilizador_db.perm_assembleias
                            st.session_state.perm_arquivo = utilizador_db.perm_arquivo
                            st.session_state.perm_fornecedores = utilizador_db.perm_fornecedores
                            st.session_state.perm_ocorrencias = utilizador_db.perm_ocorrencias
                            st.session_state.perm_mural = utilizador_db.perm_mural
                            
                            st.session_state.modo_leitura = utilizador_db.modo_leitura
                            st.session_state.perm_download_docs = utilizador_db.perm_download_docs
                            
                            registar_auditoria("LOGIN", "Sistema", "Iniciou sessão com sucesso no portal.")
                            st.rerun()
                        else: 
                            st.error("❌ Credenciais incorretas. Tente novamente.")
            
            with st.expander("Esqueceu-se da password?", expanded=False):
                st.info("ℹ️ Por motivos de segurança, a reposição de passwords é feita pela Administração.")
                            
        st.markdown("""
        <div style='text-align: center; margin-top: 15px;'>
            <p style='color: #94a3b8; font-size: 11px;'>© 2026 A3 Technologies | Versão 2.5 Premium</p>
        </div>
        """, unsafe_allow_html=True)

    # --- LAYOUT 100% CENTRALIZADO E COMPACTO ---
    col_esquerda, col_centro, col_direita = st.columns([1, 0.85, 1])
    
    with col_centro:
        if has_bg:
            text_color_title = "#ffffff"
            text_color_subtitle = "#f1f5f9"
            shadow_style = "text-shadow: 0px 2px 15px rgba(0,0,0,0.8), 0px 0px 30px rgba(0,0,0,0.9);"
        else:
            text_color_title = "#1e293b"
            text_color_subtitle = "#64748b"
            shadow_style = ""

        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 20px; {shadow_style}'>
            <h1 style='color: {text_color_title}; margin-bottom: 5px; font-size: 32px;'>{titulo_login}</h1>
            <p style='color: {text_color_subtitle}; font-size: 15px; margin-top: 0;'>Uma plataforma moderna e transparente para a gestão do seu condomínio.</p>
        </div>
        """, unsafe_allow_html=True)
        
        render_formulario_core()
        
def pagina_dashboard_morador():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    
    if not st.session_state.condomino_id:
        st.error("O seu utilizador não está associado a nenhuma fração.")
        return
    cond = session.get(Condomino, st.session_state.condomino_id)
    
    st.title(f"Bem-vindo, {cond.nome}! 👋")
    st.markdown(f"**Fração:** {cond.fracao} &nbsp;|&nbsp; **Permilagem:** {cond.permilagem}‰")
    st.markdown("<br>", unsafe_allow_html=True)
    
    if config.get("AVISO_ATIVO") and config.get("AVISO_GLOBAL"):
        # Garante que as quebras de linha inseridas no texto são respeitadas no HTML
        texto_aviso = config["AVISO_GLOBAL"].replace("\n", "<br>")
        
        st.markdown(f"""
        <div style="
            background-color: #eff6ff; 
            border-left: 6px solid #3b82f6; 
            border-radius: 8px; 
            padding: 16px 20px; 
            margin-bottom: 25px; 
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            display: flex;
            align-items: flex-start;
        ">
            <div style="font-size: 26px; margin-right: 15px; line-height: 1;">📢</div>
            <div>
                <h4 style="margin-top: 0; margin-bottom: 8px; color: #1e3a8a; font-size: 16px; font-weight: 600;">
                    Aviso à comunidade
                </h4>
                <p style="margin: 0; color: #334155; font-size: 14px; line-height: 1.5;">
                    {texto_aviso}
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # --- NOVO: GAMIFICAÇÃO / BARRA DE PROGRESSO ANUAL ---
    with st.container(border=True):
        st.subheader("🎯 O seu Progresso Anual")
        quotas_ano_atual = session.query(Quota).filter(and_(Quota.condomino_id == cond.id, Quota.mes_ano.endswith(str(ano_sel)))).all()
        
        if quotas_ano_atual:
            total_ano = len(quotas_ano_atual)
            pagas_ano = len([q for q in quotas_ano_atual if q.paga])
            percentagem = int((pagas_ano / total_ano) * 100) if total_ano > 0 else 0
            
            c_texto, c_perc = st.columns([4, 1])
            c_texto.write(f"Já regularizou **{pagas_ano} de {total_ano}** quotas referentes ao ano civil de {ano_sel}.")
            c_perc.markdown(f"<h3 style='text-align: right; margin: 0; color: #2563eb;'>{percentagem}%</h3>", unsafe_allow_html=True)
            
            st.progress(percentagem / 100.0)
            
            if percentagem == 100:
                st.success("🎉 Excelente! Tem o seu ano completamente regularizado.")
        else:
            st.info(f"Ainda não foram geradas quotas para o ano de {ano_sel}.")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- AVISO DE DÍVIDAS E DADOS DE PAGAMENTO ---
    dividas = session.query(Quota).filter_by(condomino_id=cond.id, paga=False).all()
    if dividas:
        divida_total = sum([q.valor for q in dividas])
        st.error(f"⚠️ Tem um valor total em dívida de **{divida_total:.2f} €**.")
        with st.expander(":material/account_balance: Ver Dados para Pagamento", expanded=True):
            st.write("Por favor, utilize o seguinte IBAN para regularizar a sua situação:")
            st.code(f"IBAN: {config.get('IBAN_CONDOMINIO', 'Não configurado')}", language="text")
            st.caption("Após transferência, aguarde a validação por parte da Administração.")
            
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- CONTA CORRENTE COM CARTÕES ---
    st.write("### :material/receipt_long: Histórico de Quotas")
    quotas = session.query(Quota).filter_by(condomino_id=cond.id).order_by(Quota.mes_ano.desc()).limit(12).all()
    
    if quotas:
        for q in quotas:
            with st.container(border=True):
                col_info, col_valor, col_status = st.columns([2, 1, 1])
                with col_info:
                    st.markdown(f"**Ref:** {q.mes_ano}")
                    st.caption(f"Pago a: {q.data_pagamento if q.paga else '—'}")
                with col_valor:
                    st.markdown(f"<h4 style='margin:0; color:#1e293b;'>{q.valor:.2f} €</h4>", unsafe_allow_html=True)
                with col_status:
                    if q.paga:
                        st.success("Pago", icon="✅")
                    else:
                        st.error("Pendente", icon="⏳")
    else: 
        st.info("Ainda não existem registos na sua conta corrente.")

    with st.expander(":material/key: Alterar a minha Password", expanded=False):
        with st.form("form_pwd"):
            nova_pwd = st.text_input("Nova Password", type="password", key=f"pwd1_{st.session_state.form_key}")
            conf_pwd = st.text_input("Confirmar Nova Password", type="password", key=f"pwd2_{st.session_state.form_key}")
            if st.form_submit_button("Atualizar Segurança"):
                if nova_pwd != conf_pwd: st.error("As passwords não coincidem!")
                elif len(nova_pwd) < 4: st.error("A password deve ter pelo menos 4 caracteres.")
                else:
                    utilizador_ativo = session.get(Utilizador, st.session_state.user_id)
                    utilizador_ativo.password_hash = generate_password_hash(nova_pwd)
                    session.commit()
                    registar_auditoria("ATUALIZAR", "Utilizadores", "Alterou a própria password de acesso corporativo.")
                    st.session_state.toast = ("Password updated com sucesso!", "✅")
                    st.session_state.form_key += 1
                    st.rerun()

def pagina_dashboard():
    import plotly.graph_objects as go
    
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    
    st.title("Dashboard Central")
    st.markdown(f"""
    <div style="margin-top: -15px; margin-bottom: 25px;">
        <p style="font-size: 16px; color: #64748b; font-weight: 500;">Visão global de operações referente a <strong>{mes_sel} {ano_sel}</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    if config.get("AVISO_ATIVO") and config.get("AVISO_GLOBAL"):
        # Garante que as quebras de linha inseridas no texto são respeitadas no HTML
        texto_aviso = config["AVISO_GLOBAL"].replace("\n", "<br>")
        
        st.markdown(f"""
        <div style="
            background-color: #eff6ff; 
            border-left: 6px solid #3b82f6; 
            border-radius: 8px; 
            padding: 16px 20px; 
            margin-bottom: 25px; 
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            display: flex;
            align-items: flex-start;
        ">
            <div style="font-size: 26px; margin-right: 15px; line-height: 1;">📢</div>
            <div>
                <h4 style="margin-top: 0; margin-bottom: 8px; color: #1e3a8a; font-size: 16px; font-weight: 600;">
                    Aviso à comunidade
                </h4>
                <p style="margin: 0; color: #334155; font-size: 14px; line-height: 1.5;">
                    {texto_aviso}
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # --- KPIs PRINCIPAIS ---
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
    col4.metric("Ocorrências Abertas", ocs_pendentes, f"{ocs_pendentes} pendentes", delta_color="inverse" if ocs_pendentes > 0 else "normal")
    
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
                st.subheader(f"Receitas vs Despesas [{ano_sel}]")
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
                    st.info("⚠️ Orçamento não definido. Vá a 'Finanças' para o definir.")

        st.markdown("<br>", unsafe_allow_html=True)
        r2_c1, r2_c2 = st.columns([2, 1])
        
        with r2_c1:
            with st.container(border=True):
                st.subheader("📋 Gestão Operacional")
                c_op1, c_op2 = st.columns(2)
                with c_op1:
                    st.markdown("**Ocorrências Pendentes**")
                    ocs_lista = session.query(Ocorrencia).filter_by(resolvida=False).order_by(Ocorrencia.id.desc()).limit(3).all()
                    if ocs_lista:
                        for o in ocs_lista: st.error(f"🔴 **{o.data_criacao}**: {o.titulo}")
                    else: st.success("✔️ Sem ocorrências.")
                with c_op2:
                    st.markdown("**Próximas Manutenções**")
                    ints_lista = session.query(Intervencao).filter_by(concluida=False).order_by(Intervencao.data_agendada.asc()).limit(3).all()
                    if ints_lista:
                        for i in ints_lista: st.warning(f"🟡 **{i.data_agendada}**: {i.titulo}")
                    else: st.success("✔️ Manutenções em dia.")
                    
        with r2_c2:
            with st.container(border=True):
                st.subheader("📅 Agenda & Avisos")
                ass_futuras = session.query(Assembleia).filter_by(realizada=False).order_by(Assembleia.data_agendada).limit(2).all()
                sond_ativas = session.query(Sondagem).filter_by(ativa=True).count()
                contratos_todos = session.query(Contrato).all()
                
                alertas = 0
                if contratos_todos:
                    for c in contratos_todos:
                        try:
                            dias_restantes = (datetime.strptime(c.data_fim, "%Y-%m-%d").date() - hoje).days
                            if dias_restantes < 0:
                                st.error(f"🚨 **Contrato Expirado:** '{c.titulo}' expirou!"); alertas+=1
                            elif 0 <= dias_restantes <= 30:
                                st.warning(f"⚠️ **A Expirar:** '{c.titulo}' ({dias_restantes} dias)"); alertas+=1
                        except: pass

                if ass_futuras:
                    for a in ass_futuras:
                        try:
                            dias_restantes = (datetime.strptime(a.data_agendada, "%Y-%m-%d").date() - hoje).days
                            if dias_restantes == 0: st.warning(f"🚨 **Assembleia HOJE:** {a.titulo}"); alertas+=1
                            elif dias_restantes > 0: st.info(f"⏳ **Reunião em {dias_restantes} dias:** {a.titulo}"); alertas+=1
                        except: pass
                
                if sond_ativas > 0:
                    st.success(f"🗳️ **{sond_ativas} votações ativas** no portal."); alertas+=1
                    
                if alertas == 0: st.info("Sem marcações na agenda.")

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

def pagina_acessos():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/admin_panel_settings: Gestão de Acessos e Permissões")
    
    tab_users, tab_perms = st.tabs([":material/person_add: Criar Utilizadores", ":material/shield: Configurar Permissões"])
    
    with tab_users:
        conds = session.query(Condomino).all()
        if conds:
            df_acessos = pd.DataFrame([{"ID": c.id, "Fração": c.fracao, "Proprietário": c.nome, "Tem Acesso?": "✅ Sim" if session.query(Utilizador).filter_by(condomino_id=c.id).first() else "❌ Não", "Username": session.query(Utilizador).filter_by(condomino_id=c.id).first().username if session.query(Utilizador).filter_by(condomino_id=c.id).first() else "—"} for c in conds])
            with st.container(border=True):
                ev_acesso = st.dataframe(df_acessos, width="stretch", hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
            if ev_acesso.selection.rows:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.container(border=True):
                    id_cond = int(df_acessos.iloc[ev_acesso.selection.rows[0]]["ID"])
                    cond_sel = session.get(Condomino, id_cond)
                    user_existente = session.query(Utilizador).filter_by(condomino_id=id_cond).first()
                    st.info(f":material/push_pin: A gerir acesso de: **{cond_sel.fracao} ({cond_sel.nome})**")
                    if not user_existente:
                        st.warning("Este morador ainda não tem acesso ao portal.")
                        if st.button(":material/rocket_launch: Criar Utilizador", width="stretch"):
                            username_sugerido = formatar_username(cond_sel.nome)
                            sucesso, msg_toast = False, ""
                            
                            novo_user = Utilizador(
                                username=username_sugerido, password_hash=generate_password_hash("mudar123"), 
                                perfil="Morador", condomino_id=id_cond,
                                perm_dashboard=True, perm_condominos=False, 
                                perm_quotas=True, perm_financas=False, perm_recibos=True,
                                perm_assembleias=True, perm_arquivo=True, perm_fornecedores=False, perm_ocorrencias=True,
                                perm_mural=True,
                                modo_leitura=False, perm_download_docs=True
                            )
                            try:
                                session.add(novo_user); session.commit()
                                registar_auditoria("CRIAR", "Utilizadores", f"Criou o utilizador morador '{novo_user.username}' para a fração {cond_sel.fracao}.")
                                sucesso, msg_toast = True, f"Acesso criado! Login: {novo_user.username} | Pass: mudar123"
                            except Exception:
                                session.rollback()
                                novo_user_alt = Utilizador(
                                    username=f"{username_sugerido}_{cond_sel.fracao.replace(' ', '').lower()}", 
                                    password_hash=generate_password_hash("mudar123"), perfil="Morador", condomino_id=id_cond,
                                    perm_dashboard=True, perm_condominos=False, 
                                    perm_quotas=True, perm_financas=False, perm_recibos=True,
                                    perm_assembleias=True, perm_arquivo=True, perm_fornecedores=False, perm_ocorrencias=True,
                                    perm_mural=True,
                                    modo_leitura=False, perm_download_docs=True
                                )
                                try:
                                    session.add(novo_user_alt); session.commit()
                                    registar_auditoria("CRIAR", "Utilizadores", f"Criou o utilizador morador alternativo '{novo_user_alt.username}' para a fração {cond_sel.fracao}.")
                                    sucesso, msg_toast = True, f"Acesso criado! Login: {novo_user_alt.username} | Pass: mudar123"
                                except Exception as e2: 
                                    session.rollback()
                                    st.error(f"Erro técnico na base de dados: {str(e2)}")
                            if sucesso: st.session_state.toast = (msg_toast, "✅"); st.rerun()
                    else:
                        c1, c2 = st.columns(2)
                        if c1.button("Repor Password para 'mudar123'", width="stretch"): 
                            user_existente.password_hash = generate_password_hash("mudar123")
                            session.commit()
                            registar_auditoria("ATUALIZAR", "Utilizadores", f"Repôs a password do utilizador '{user_existente.username}' para o valor padrão.")
                            st.session_state.toast = ("Reposta!", "✅"); st.rerun()
                        if c2.button("Remover Acesso", width="stretch"): 
                            u_nome = user_existente.username
                            session.delete(user_existente); session.commit()
                            registar_auditoria("APAGAR", "Utilizadores", f"Apagou permanentemente o acesso do utilizador '{u_nome}'.")
                            st.session_state.toast = ("Removido.", "🗑️"); st.rerun()
        else: st.info("Ainda não tem condóminos.")

    with tab_perms:
        users = session.query(Utilizador).filter_by(perfil="Morador").all()
        if users:
            df_perms = pd.DataFrame([{"ID_User": u.id, "Fração": u.condomino.fracao if u.condomino else "N/A", "Username": u.username, "Leitura": "👁️ Ativo" if u.modo_leitura else "✏️ Não"} for u in users])
            with st.container(border=True):
                ev_perms = st.dataframe(df_perms, width="stretch", hide_index=True, column_config={"ID_User": None}, on_select="rerun", selection_mode="single-row")
            if ev_perms.selection.rows:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.container(border=True):
                    u_sel = session.get(Utilizador, int(df_perms.iloc[ev_perms.selection.rows[0]]["ID_User"]))
                    with st.form("form_perms"):
                        st.subheader(f":material/shield: Permissões Específicas de: {u_sel.username}")
                        
                        st.write("---")
                        st.write("**Restrições Globais de Ação:**")
                        val_leitura = st.checkbox(":material/visibility: Modo Leitura Global (Apenas visualiza dados)", value=u_sel.modo_leitura, key=f"p_l_{st.session_state.form_key}")
                        val_down = st.checkbox(":material/download: Permitir Descarregar Documentos PDF", value=u_sel.perm_download_docs, key=f"p_d_{st.session_state.form_key}")
                        
                        st.write("---")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write("**Visão Geral**")
                            val_dash = st.checkbox("Dashboard", value=u_sel.perm_dashboard, key=f"p_dash_{st.session_state.form_key}")
                            val_cond = st.checkbox("Condóminos", value=u_sel.perm_condominos, key=f"p_cond_{st.session_state.form_key}")
                        with col2:
                            st.write("**Tesouraria**")
                            val_quotas = st.checkbox("Gestão de Quotas", value=u_sel.perm_quotas, key=f"p_quotas_{st.session_state.form_key}")
                            val_fin = st.checkbox("Finanças & Extratos", value=u_sel.perm_financas, key=f"p_fin_{st.session_state.form_key}")
                            val_rec = st.checkbox("Emissão de Recibos", value=u_sel.perm_recibos, key=f"p_rec_{st.session_state.form_key}")
                        with col3:
                            st.write("**Operações**")
                            val_mur = st.checkbox("Mural da Comunidade", value=u_sel.perm_mural, key=f"p_mur_{st.session_state.form_key}")
                            val_ass = st.checkbox("Assembleias & Votações", value=u_sel.perm_assembleias, key=f"p_ass_{st.session_state.form_key}")
                            val_arq = st.checkbox("Arquivo Digital", value=u_sel.perm_arquivo, key=f"p_arq_{st.session_state.form_key}")
                            val_forn = st.checkbox("Fornecedores", value=u_sel.perm_fornecedores, key=f"p_forn_{st.session_state.form_key}")
                            val_oco = st.checkbox("Ocorrências", value=u_sel.perm_ocorrencias, key=f"p_oco_{st.session_state.form_key}")

                        if st.form_submit_button("Guardar Permissões Segmentadas", width="stretch"):
                            u_sel.modo_leitura = val_leitura
                            u_sel.perm_download_docs = val_down
                            u_sel.perm_dashboard, u_sel.perm_condominos = val_dash, val_cond
                            u_sel.perm_quotas, u_sel.perm_financas, u_sel.perm_recibos = val_quotas, val_fin, val_rec
                            u_sel.perm_mural, u_sel.perm_assembleias = val_mur, val_ass
                            u_sel.perm_arquivo, u_sel.perm_fornecedores, u_sel.perm_ocorrencias = val_arq, val_forn, val_oco
                            session.commit()
                            registar_auditoria("ATUALIZAR", "Utilizadores", f"Modificou a matriz de permissões do utilizador '{u_sel.username}'.")
                            st.session_state.toast = ("Permissões atualizadas com sucesso!", "✅")
                            st.session_state.form_key += 1
                            st.rerun()
        else: st.info("Sem moradores com acesso.")

def pagina_condominos():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/group: Gestão de Condóminos")
    
    # --- NOVO: Campo de Pesquisa Ativa na Sidebar ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Procurar Morador")
    pesquisa_termo = st.sidebar.text_input(
        "Fração ou Nome do Proprietário:", 
        placeholder="Ex: 2º Esq",
        key=f"sidebar_search_cond_{st.session_state.form_key}"
    ).strip().lower()
    
    if not st.session_state.modo_leitura and st.session_state.perfil == "Admin":
        with st.expander(":material/upload_file: Importar Moradores via Excel/CSV"):
            st.write("Faça upload de um ficheiro CSV ou Excel contendo as seguintes colunas (exatamente com estes nomes): `Nome,Fração,NIF,Telefone,Email,Permilagem`.")
            ficheiro_import = st.file_uploader("Escolher ficheiro", type=["csv", "xlsx"], key=f"file_up_{st.session_state.form_key}")
            if ficheiro_import is not None:
                if st.button("Processar Importação", width="stretch"):
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
                            registar_auditoria("CRIAR", "Condóminos", f"Importou {novos} condóminos em lote via ficheiro.")
                            st.success(f"{novos} frações importadas com sucesso!")
                            st.session_state.form_key += 1
                        else:
                            st.warning("Não foram importadas frações (já existem ou ficheiro sem dados válidos).")
                    except Exception as e:
                        st.error(f"Erro ao processar o ficheiro. Detalhe técnico: {e}")
    
    # Aplica o filtro de texto diretamente à query SQL (case-insensitive parcial)
    query_conds = session.query(Condomino)
    if pesquisa_termo:
        query_conds = query_conds.filter(
            or_(
                func.lower(Condomino.fracao).like(f"%{pesquisa_termo}%"),
                func.lower(Condomino.nome).like(f"%{pesquisa_termo}%")
            )
        )
    conds = query_conds.all()
    
    total_permilagem = session.query(func.sum(Condomino.permilagem)).scalar() or 0.0
    col_kpi1, col_kpi2 = st.columns([3, 1])
    col_kpi1.info(f"Permilagem Total Registada: **{total_permilagem:.2f} / 1000**")
    
    if not st.session_state.modo_leitura:
        title_form = ":material/edit: Editar Condómino" if st.session_state.edit_type == "cond" else ":material/person_add: Registo Manual"
        with st.expander(title_form, expanded=(st.session_state.edit_type == "cond")):
            with st.form("f_cond"):
                val_n, val_f, val_nif, val_t, val_e, val_p = "", "", "", "", "", 0.0
                if st.session_state.edit_type == "cond":
                    obj = session.get(Condomino, st.session_state.edit_id)
                    val_n, val_f, val_nif, val_t, val_e, val_p = obj.nome, obj.fracao, obj.nif, obj.telefone, obj.email, obj.permilagem

                c_form1, c_form2 = st.columns(2)
                with c_form1:
                    n = st.text_input("Nome do Proprietário", value=val_n, key=f"c_n_{st.session_state.form_key}")
                    f = st.text_input("Fração (Ex: 1º Esq)", value=val_f, key=f"c_f_{st.session_state.form_key}")
                    p = st.number_input("Permilagem (ex: 50.5)", value=float(val_p), min_value=0.0, max_value=1000.0, format="%.2f", key=f"c_p_{st.session_state.form_key}")
                with c_form2:
                    nif_input = st.text_input("NIF", value=val_nif, key=f"c_nif_{st.session_state.form_key}")
                    t = st.text_input("Telefone", value=val_t, key=f"c_t_{st.session_state.form_key}")
                    e = st.text_input("Email", value=val_e, key=f"c_e_{st.session_state.form_key}")
                
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Guardar"):
                    if st.session_state.edit_type == "cond":
                        obj.nome, obj.fracao, obj.nif, obj.telefone, obj.email, obj.permilagem = n, f, nif_input, t, e, p
                        session.commit()
                        registar_auditoria("ATUALIZAR", "Condóminos", f"Editou os dados da fração {f} ({n}).")
                        st.session_state.toast = ("Condómino atualizado!", "✏️")
                    else:
                        session.add(Condomino(nome=n, fracao=f, nif=nif_input, telefone=t, email=e, permilagem=p))
                        session.commit()
                        registar_auditoria("CRIAR", "Condóminos", f"Criou manualmente o registo da fração {f} ({n}).")
                        st.session_state.toast = ("Condómino adicionado!", "✅")
                    clear_edit(); st.rerun()
                if c2.form_submit_button("Cancelar"): clear_edit(); st.rerun()

    if conds:
        with st.container(border=True):
            df_export = pd.DataFrame([{"ID": c.id, "Fração": c.fracao, "Nome": c.nome, "NIF": c.nif, "Permilagem": c.permilagem, "Telefone": c.telefone, "Email": c.email} for c in conds])
            evento = st.dataframe(df_export, width="stretch", hide_index=True, column_config={"ID": None, "Permilagem": st.column_config.NumberColumn("Permilagem (‰)", format="%.2f ‰")}, on_select="rerun", selection_mode="single-row")
        
        if evento.selection.rows:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                id_sel = int(df_export.iloc[evento.selection.rows[0]]["ID"])
                cond_obj = session.get(Condomino, id_sel)
                c_info, c_edit, c_del = st.columns([2, 1, 1])
                c_info.info(f":material/push_pin: Selecionado: **{cond_obj.fracao} - {cond_obj.nome}**")
                if not st.session_state.modo_leitura:
                    if c_edit.button(":material/edit: Editar Fração", width="stretch"):
                        st.session_state.edit_id = id_sel; st.session_state.edit_type = "cond"; st.session_state.form_key += 1; st.rerun()
                    if c_del.button(":material/delete: Apagar Registo", width="stretch"):
                        f_info = f"{cond_obj.fracao} ({cond_obj.nome})"
                        session.delete(cond_obj); session.commit()
                        registar_auditoria("APAGAR", "Condóminos", f"Apagou o registo físico da fração {f_info}.")
                        st.session_state.toast = ("Registo apagado!", "🗑️"); st.rerun()
    else: st.info("Ainda não existem condóminos registados ou encontrados para a pesquisa.")

def pagina_quotas():
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
        st.warning("⚠️ **Nenhum condómino registado:** Vá ao separador **Condóminos** para registar ou importar frações.")
        return

    condominos_sem_quota = [c for c in condominos if not session.query(Quota).filter_by(condomino_id=c.id, mes_ano=mes_str).first()]
    
    if st.session_state.perfil == "Admin":
        with st.container(border=True):
            st.subheader(":material/precision_manufacturing: Gerador de Quotas")
            if len(condominos_sem_quota) > 0: st.warning(f"O sistema detetou **{len(condominos_sem_quota)} fração(ões)** sem quota processada neste mês.")
            else: st.success(f"As quotas do mês {mes_str} já estão processadas.")
            if not st.session_state.modo_leitura:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f":material/bolt: Gerar Quotas Apenas de {mes_str}", width="stretch"):
                        if len(condominos_sem_quota) > 0:
                            for c in condominos_sem_quota: session.add(Quota(condomino_id=c.id, mes_ano=mes_str, valor=valor_quota_padrao, paga=False))
                            session.commit()
                            registar_auditoria("CRIAR", "Quotas", f"Gerou em lote as quotas para o mês {mes_str}.")
                            st.session_state.toast = (f"Quotas de {mes_str} geradas!", "✅"); st.rerun()
                        else: st.info("Não há quotas em falta.")
                with col2:
                    if st.button(f":material/calendar_month: Gerar para Todo o Ano de {ano_sel}", width="stretch", type="primary"):
                        with st.spinner("A processar faturas para todo o ano... por favor aguarde."):
                            novas_quotas = 0
                            for c in condominos:
                                for m in range(1, 13):
                                    m_str = f"{m:02d}/{ano_sel}"
                                    if not session.query(Quota).filter_by(condomino_id=c.id, mes_ano=m_str).first():
                                        session.add(Quota(condomino_id=c.id, mes_ano=m_str, valor=valor_quota_padrao, paga=False))
                                        novas_quotas += 1
                            if novas_quotas > 0: 
                                session.commit()
                                registar_auditoria("CRIAR", "Quotas", f"Gerou em lote as quotas do ano {ano_sel} ({novas_quotas} novas quotas).")
                                st.session_state.toast = (f"{novas_quotas} quotas geradas!", "🎉")
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
                if st.button("Disparar Avisos para Todos os Devedores", width="stretch", type="primary"):
                    with st.spinner("A enviar emails..."):
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
                evento_divida = st.dataframe(df_dividas, width="stretch", hide_index=True, column_config={"ID": None, "Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")}, on_select="rerun", selection_mode="single-row")
            if evento_divida.selection.rows:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.container(border=True):
                    quota_obj = session.get(Quota, int(df_dividas.iloc[evento_divida.selection.rows[0]]["ID"]))
                    st.info(f":material/push_pin: Selecionado: **Fração {quota_obj.condomino.fracao}** ({quota_obj.mes_ano}) - **{quota_obj.valor:.2f} €**")
                    col_pagar, col_aviso = st.columns(2)
                    if not st.session_state.modo_leitura:
                        if col_pagar.button(":material/done: Marcar como Paga", width="stretch"):
                            quota_obj.paga = True; quota_obj.data_pagamento = hoje.strftime("%Y-%m-%d")
                            session.commit()
                            registar_auditoria("ATUALIZAR", "Quotas", f"Marcou como paga a quota {quota_obj.mes_ano} da fração {quota_obj.condomino.fracao} no valor de {quota_obj.valor}€.")
                            st.rerun()
                        if st.session_state.perfil == "Admin":
                            with col_aviso.popover(":material/mail: Enviar Aviso Individual"):
                                corpo_email = f"Exmo(a) Sr(a) {quota_obj.condomino.nome},\n\nEncontra-se a pagamento a quota de {quota_obj.mes_ano} no valor de {quota_obj.valor:.2f} €.\n\nPor favor, proceda à transferência para o seguinte IBAN: {config.get('IBAN_CONDOMINIO', 'N/D')}\n\nA Administração."
                                st.markdown(f"**Mensagem:**\n\n{corpo_email}")
                                if st.button("Confirmar Envio", key=f"mail_aviso_{quota_obj.id}", width="stretch"):
                                    if quota_obj.condomino.email:
                                        if enviar_email_real(quota_obj.condomino.email, f"Aviso de Pagamento - {quota_obj.mes_ano}", corpo_email): st.toast("Enviado!", icon="✅")
                                    else: st.error("Sem email registado.")
        else: st.success("🎉 Não existem quotas em dívida.")

    with tab_pagas:
        pagas = pagas_query.all()
        if pagas:
            with st.container(border=True):
                df_pagas = pd.DataFrame([{"Data": p.data_pagamento, "Referência": p.mes_ano, "Fração": p.condomino.fracao, "Nome": p.condomino.nome, "Valor": p.valor} for p in pagas])
                st.dataframe(df_pagas, width="stretch", hide_index=True, column_config={"Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")})

def pagina_financas():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/account_balance: Finanças e Fluxo de Caixa")
    
    tab_mes, tab_ano = st.tabs([f"📅 Extrato Mensal ({mes_sel})", f"📈 Relatório Anual (Fecho de Contas {ano_sel})"])

    with tab_mes:
        if not st.session_state.modo_leitura and st.session_state.perfil == "Admin":
            orc = session.query(Orcamento).filter_by(ano=ano_sel).first()
            with st.expander(f":material/assignment: Definir Orçamento Anual de {ano_sel}", expanded=(not orc)):
                with st.form("f_orc"):
                    v_orc = st.number_input(f"Valor do Orçamento Aprovado (€)", value=orc.valor_anual if orc else 0.0, step=100.0, key=f"o_v_{st.session_state.form_key}")
                    if st.form_submit_button("Guardar Orçamento"):
                        if orc: orc.valor_anual = v_orc
                        else: session.add(Orcamento(ano=ano_sel, valor_anual=v_orc))
                        session.commit()
                        registar_auditoria("ATUALIZAR", "Orçamentos", f"Definiu o orçamento anual para {ano_sel} no valor de {v_orc:.2f}€.")
                        st.session_state.form_key += 1; st.rerun()

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
                        t = st.radio("Tipo de Lançamento", ["Despesa", "Receita"], horizontal=True, key=f"m_t_{st.session_state.form_key}")
                        d = st.text_input("Descrição *", key=f"m_d_{st.session_state.form_key}")
                        v = st.number_input("Valor (€) *", min_value=0.00, value=0.00, step=10.0, format="%.2f", key=f"m_v_{st.session_state.form_key}")
                        dt = st.date_input("Data do Movimento", value=hoje, key=f"m_dt_{st.session_state.form_key}")
                        if st.form_submit_button("Registar Lançamento"):
                            if not d.strip(): st.error("⚠️ O preenchimento da Descrição é obrigatório!")
                            elif v <= 0.0: st.error("⚠️ O valor do lançamento tem de ser superior a 0,00 €!")
                            else:
                                session.add(Movimento(tipo=t, descricao=d, valor=v, data=dt.strftime("%Y-%m-%d")))
                                session.commit()
                                registar_auditoria("CRIAR", "Finanças", f"Lançou manualmente uma {t.lower()} ('{d}') de {v:.2f}€.")
                                st.session_state.toast = ("Lançamento registado com sucesso!", "✅")
                                st.session_state.form_key += 1; st.rerun()

            with c_add_imp:
                with st.expander(":material/upload_file: Importar Extrato Bancário", expanded=False):
                    st.write("Faça upload de um ficheiro com as colunas exatas: `Tipo,Descrição,Valor,Data`.")
                    ficheiro_import_fin = st.file_uploader("Escolher ficheiro financeiro", type=["csv", "xlsx"], key=f"file_up_fin_{st.session_state.form_key}")
                    if ficheiro_import_fin is not None:
                        if st.button("Processar Importação", width="stretch", type="primary"):
                            with st.spinner("A processar movimentos..."):
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
                                        registar_auditoria("CRIAR", "Finanças", f"Importou {novos_movs} movimentos em lote via extrato bancário.")
                                        st.success(f"{novos_movs} movimentos importados com sucesso!")
                                        st.session_state.form_key += 1
                                        st.rerun()
                                    else:
                                        st.warning("Não foram importados registos válidos.")
                                except Exception as e:
                                    st.error(f"Erro ao processar o ficheiro: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- NOVO: Filtro Contextual Inteligente na Sidebar ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("📈 Tipo de Fluxo")
        filtro_fin = st.sidebar.selectbox(
            "Filtrar Extrato:",
            ["Todos os Movimentos", "💸 Apenas Despesas", "💰 Apenas Receitas"],
            key=f"sidebar_filter_fin_{st.session_state.form_key}"
        )

        movs_query = session.query(Movimento).filter(and_(Movimento.data >= str_inicio, Movimento.data < str_fim))
        
        q_ant = session.query(func.sum(Quota.valor)).filter(and_(Quota.paga == True, Quota.data_pagamento < str_inicio)).scalar() or 0.0
        rec_ant = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Receita", Movimento.data < str_inicio)).scalar() or 0.0
        desp_ant = session.query(func.sum(Movimento.valor)).filter(and_(Movimento.tipo == "Despesa", Movimento.data < str_inicio)).scalar() or 0.0
        saldo_anterior = (q_ant + rec_ant) - desp_ant
        
        q_atual = session.query(func.sum(Quota.valor)).filter(and_(Quota.paga == True, Quota.data_pagamento >= str_inicio, Quota.data_pagamento < str_fim)).scalar() or 0.0

        extrato_data = []
        if "Despesas" not in filtro_fin:
            if q_atual > 0 or filtro_fin == "Todos os Movimentos":
                extrato_data.append({"ID": "-", "Data": "-", "Tipo": "Receita (Quotas)", "Descrição": "Soma Quotas Mensais", "Valor": q_atual})
        
        if "Despesas" in filtro_fin:
            movs = movs_query.filter(Movimento.tipo == "Despesa").all()
        elif "Receitas" in filtro_fin:
            movs = movs_query.filter(Movimento.tipo == "Receita").all()
        else:
            movs = movs_query.all()

        if movs: 
            extrato_data.extend([{"ID": m.id, "Data": m.data, "Tipo": m.tipo, "Descrição": m.descricao, "Valor": m.valor} for m in movs])
        
        df_extrato = pd.DataFrame(extrato_data) if extrato_data else pd.DataFrame(columns=["ID", "Data", "Tipo", "Descrição", "Valor"])

        col_tit, col_btn = st.columns([3, 1])
        with col_tit:
            st.subheader(f"Movimentos de {mes_sel} {ano_sel}")
            st.write(f"**Saldo Transitado do Mês Anterior:** {saldo_anterior:.2f} €")
            st.write(f"**(+) Total Quotas Recebidas no Mês:** {q_atual:.2f} €")
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if REPORTLAB_INSTALLED and not df_extrato.empty:
                pdf_bytes = gerar_pdf_extrato(df_extrato, mes_sel, ano_sel, saldo_anterior)
                if pdf_bytes: st.download_button(":material/picture_as_pdf: Exportar PDF (Mês)", data=pdf_bytes, file_name=f"Extrato_{mes_sel}_{ano_sel}.pdf", mime="application/pdf", width="stretch")
        
        if not df_extrato.empty:
            with st.container(border=True):
                evento_fin = st.dataframe(df_extrato, width="stretch", hide_index=True, column_config={"ID": None, "Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")}, on_select="rerun", selection_mode="single-row")
            if evento_fin.selection.rows and not st.session_state.modo_leitura and st.session_state.perfil == "Admin":
                id_mov = df_extrato.iloc[evento_fin.selection.rows[0]]["ID"]
                if id_mov != "-": 
                    with st.container(border=True):
                        mov_obj = session.get(Movimento, int(id_mov))
                        if st.button(f":material/delete: Apagar {mov_obj.descricao}", width="stretch"): 
                            m_info = f"{mov_obj.tipo} - '{mov_obj.descricao}' ({mov_obj.valor:.2f}€)"
                            session.delete(mov_obj); session.commit()
                            registar_auditoria("APAGAR", "Finanças", f"Apagou o movimento financeiro: {m_info}.")
                            st.rerun()

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
                st.download_button("📥 Descarregar Relatório de Contas (PDF)", data=pdf_bytes_anual, file_name=f"Relatorio_Contas_{ano_sel}.pdf", mime="application/pdf", width="stretch")
            
            with col_mail:
                if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
                    if st.button("📧 Enviar Relatório por Email a Todos", width="stretch", type="primary"):
                        with st.spinner("A enviar relatório para todos os condóminos..."):
                            condominos_com_email = session.query(Condomino).filter(Condomino.email.isnot(None), Condomino.email != "").all()
                            emails_enviados = 0
                            for c in condominos_com_email:
                                corpo_email = f"Exmo(a) Sr(a) {c.nome},\n\nJunto enviamos o Relatório de Contas Anual referente ao ano de {ano_sel}.\n\nCumprimentos,\nA Administração."
                                if enviar_email_real(c.email, f"Relatório de Contas Anual - {ano_sel}", corpo_email, anexo_bytes=pdf_bytes_anual, nome_anexo=f"Relatorio_Contas_{ano_sel}.pdf"):
                                    emails_enviados += 1
                            if emails_enviados > 0: st.success(f"Relatório enviado a {emails_enviados} condóminos com sucesso!")
                            else: st.warning("Não existem condóminos com email registado.")
        
        with st.container(border=True):
            st.write("**Detalhamento das Despesas do Ano:**")
            if not df_desp_agrupadas.empty:
                st.dataframe(df_desp_agrupadas, width="stretch", hide_index=True, column_config={"Valor": st.column_config.NumberColumn("Valor Total Pago no Ano (€)", format="%.2f €")})
            else:
                st.info("Ainda não existem despesas registadas neste ano civil.")

def pagina_recibos():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/receipt_long: Emissão de Recibos")
    if st.session_state.perfil == "Admin":
        q_pagas = session.query(Quota).filter(Quota.paga == True).order_by(Quota.data_pagamento.desc()).all()
    else:
        q_pagas = session.query(Quota).filter(and_(Quota.paga == True, Quota.condomino_id == st.session_state.condomino_id)).order_by(Quota.data_pagamento.desc()).all()
    
    if not q_pagas: st.warning("Ainda não existem quotas pagas registadas no sistema.")
    else:
        st.write(":material/touch_app: **Clique numa linha para gerar e visualizar o recibo de pagamento:**")
        with st.container(border=True):
            df_recibos = pd.DataFrame([{"ID": q.id, "Data Pagamento": q.data_pagamento, "Ref. Mensal": q.mes_ano, "Fração": q.condomino.fracao, "Nome": q.condomino.nome, "Valor": q.valor} for q in q_pagas])
            evento_rec = st.dataframe(df_recibos, width="stretch", hide_index=True, column_config={"ID": None, "Valor": st.column_config.NumberColumn("Valor (€)", format="%.2f €")}, on_select="rerun", selection_mode="single-row")
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
                        st.download_button(":material/download: Descarregar Recibo (PDF)", data=pdf_bytes, file_name=f"{nome_pdf}.pdf", mime="application/pdf", width="stretch")
                with col2:
                    st.write("#### :material/mail: 2. Enviar por Email")
                    if not st.session_state.modo_leitura:
                        if st.session_state.perfil == "Admin":
                            if st.button(":material/send: Enviar Confirmação Simples", width="stretch"):
                                with st.spinner("A enviar email..."):
                                    if q.condomino.email:
                                        corpo = f"Exmo(a) Sr(a) {q.condomino.nome},\nConfirmamos o pagamento da quota de {q.mes_ano}, no valor de {q.valor:.2f} €.\nA Administração."
                                        if enviar_email_real(q.condomino.email, f"Confirmação de Pagamento - {q.mes_ano}", corpo): st.toast("Enviado!", icon="✅")
                                    else: st.error("Sem email registado.")
                            if REPORTLAB_INSTALLED:
                                if st.button("📧 Enviar Recibo com PDF Anexo", type="primary", width="stretch"):
                                    with st.spinner("A gerar PDF e a enviar email..."):
                                        if q.condomino.email:
                                            corpo = f"Exmo(a) Sr(a) {q.condomino.nome},\nSegue em anexo o recibo oficial em PDF.\nA Administração."
                                            if enviar_email_real(q.condomino.email, f"Recibo Oficial de Pagamento - {q.mes_ano}", corpo, anexo_bytes=pdf_bytes, nome_anexo=f"{nome_pdf}.pdf"): st.toast("Enviado!", icon="🎉")
                                        else: st.error("Condómino sem email.")

def pagina_documentos():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/folder_open: Arquivo Digital de Documentos")
    
    if not st.session_state.modo_leitura:
        with st.expander(":material/note_add: Arquivar Novo Documento", expanded=False):
            with st.form("form_upload"):
                st.text_input("Carregado por", value=st.session_state.username, disabled=True)
                categoria = st.selectbox("Categoria", ["Atas de Assembleia", "Apólices de Seguro", "Faturas e Recibos", "Contratos", "Manuais", "Outros"], key=f"d_cat_{st.session_state.form_key}")
                ficheiro = st.file_uploader("Selecione o ficheiro", type=["pdf", "jpg", "png", "jpeg"], key=f"d_f_{st.session_state.form_key}")
                
                if st.form_submit_button("Guardar Documento") and ficheiro is not None:
                    if not os.path.exists("uploads"): os.makedirs("uploads")
                    caminho = os.path.join("uploads", ficheiro.name)
                    with open(caminho, "wb") as f: f.write(ficheiro.getbuffer())
                    
                    session.add(Documento(nome_ficheiro=ficheiro.name, categoria=categoria, caminho=caminho, carregado_por=st.session_state.username))
                    session.commit()
                    registar_auditoria("CRIAR", "Arquivo", f"Arquivou o documento '{ficheiro.name}' na categoria '{categoria}'.")
                    st.session_state.form_key += 1; st.rerun()

    docs = session.query(Documento).order_by(Documento.id.desc()).all()
    if docs:
        with st.container(border=True):
            df_docs = pd.DataFrame([{"ID": d.id, "Data": d.data_upload, "Categoria": d.categoria, "Nome": d.nome_ficheiro, "Utilizador": d.carregado_por if d.carregado_por else "Sistema/Antigo"} for d in docs])
            evento_doc = st.dataframe(df_docs, width="stretch", hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
        
        if evento_doc.selection.rows:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                doc_obj = session.get(Documento, int(df_docs.iloc[evento_doc.selection.rows[0]]["ID"]))
                col_info, col_down, col_del = st.columns([2, 1, 1])
                
                utilizador_txt = doc_obj.carregado_por if doc_obj.carregado_por else "Sistema/Antigo"
                col_info.info(f":material/push_pin: Selecionado: **{doc_obj.nome_ficheiro}** | Carregado por: **{utilizador_txt}**")
                
                if st.session_state.perm_download_docs:
                    try:
                        with open(doc_obj.caminho, "rb") as file: col_down.download_button("📥 Baixar", data=file, file_name=doc_obj.nome_ficheiro, width="stretch")
                    except FileNotFoundError: col_down.error("Ficheiro físico não encontrado.")
                else: col_down.warning("🚫 Sem permissão de download")
                    
                if not st.session_state.modo_leitura:
                    pode_apagar = (st.session_state.perfil == "Admin") or (doc_obj.carregado_por == st.session_state.username)
                    if pode_apagar:
                        if col_del.button("🗑️ Apagar", width="stretch"):
                            if os.path.exists(doc_obj.caminho): os.remove(doc_obj.caminho) 
                            doc_nome = doc_obj.nome_ficheiro
                            session.delete(doc_obj); session.commit()
                            registar_auditoria("APAGAR", "Arquivo", f"Eliminou permanentemente o documento '{doc_nome}' do servidor.")
                            st.rerun()
    else: st.info("O arquivo está vazio.")

def pagina_fornecedores():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/contact_phone: Fornecedores e Contratos")
    
    tab_diretorio, tab_contratos = st.tabs(["📇 Diretório de Contactos", "📑 Contratos de Manutenção"])
    
    # ==========================================
    # TAB 1: DIRETÓRIO DE FORNECEDORES
    # ==========================================
    with tab_diretorio:
        if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
            title_form = ":material/edit: Editar Fornecedor" if st.session_state.edit_type == "forn" else ":material/person_add: Novo Fornecedor"
            with st.expander(title_form, expanded=(st.session_state.edit_type == "forn")):
                with st.form("f_forn"):
                    val_n, val_cat, val_t, val_e, val_nif, val_obs, val_resp, val_iban = "", "Geral", "", "", "", "", "", ""
                    if st.session_state.edit_type == "forn":
                        obj = session.get(Fornecedor, st.session_state.edit_id)
                        val_n, val_cat, val_t, val_e, val_nif, val_obs = obj.nome, obj.categoria, obj.telefone, obj.email, obj.nif, obj.observacoes
                        val_resp, val_iban = obj.responsavel, obj.iban

                    c_form1, c_form2 = st.columns(2)
                    with c_form1:
                        n = st.text_input("Nome da Empresa / Profissional *", value=val_n, key=f"f_n_{st.session_state.form_key}")
                        cat = st.selectbox("Categoria", ["Eletricista", "Canalizador", "Limpeza", "Elevadores", "Seguros", "Geral", "Outro"], index=["Eletricista", "Canalizador", "Limpeza", "Elevadores", "Seguros", "Geral", "Outro"].index(val_cat) if val_cat else 5, key=f"f_cat_{st.session_state.form_key}")
                        resp = st.text_input("Responsável de Contacto", value=val_resp, key=f"f_resp_{st.session_state.form_key}")
                        t = st.text_input("Telefone", value=val_t, key=f"f_t_{st.session_state.form_key}")
                    with c_form2:
                        e = st.text_input("Email", value=val_e, key=f"f_e_{st.session_state.form_key}")
                        nif_input = st.text_input("NIF", value=val_nif, key=f"f_nif_{st.session_state.form_key}")
                        iban_input = st.text_input("IBAN", value=val_iban, key=f"f_iban_{st.session_state.form_key}")
                        obs = st.text_area("Observações", value=val_obs, key=f"f_obs_{st.session_state.form_key}")
                    
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Guardar Fornecedor"):
                        if not n.strip(): st.error("O nome é obrigatório.")
                        else:
                            if st.session_state.edit_type == "forn":
                                obj.nome, obj.categoria, obj.telefone, obj.email, obj.nif, obj.observacoes = n, cat, t, e, nif_input, obs
                                obj.responsavel, obj.iban = resp, iban_input
                                session.commit()
                                registar_auditoria("ATUALIZAR", "Fornecedores", f"Editou os dados cadastrais do fornecedor '{n}'.")
                                st.session_state.toast = ("Fornecedor atualizado!", "✏️")
                            else:
                                session.add(Fornecedor(nome=n, categoria=cat, telefone=t, email=e, nif=nif_input, observacoes=obs, responsavel=resp, iban=iban_input))
                                session.commit()
                                registar_auditoria("CRIAR", "Fornecedores", f"Adicionou um novo fornecedor '{n}' ({cat}).")
                                st.session_state.toast = ("Fornecedor adicionado!", "✅")
                            clear_edit(); st.rerun()
                    if c2.form_submit_button("Cancelar"): clear_edit(); st.rerun()

        fornecedores = session.query(Fornecedor).all()
        if fornecedores:
            with st.container(border=True):
                df_export = pd.DataFrame([{"ID": f.id, "Categoria": f.categoria, "Nome": f.nome, "Telefone": f.telefone, "Email": f.email} for f in fornecedores])
                evento = st.dataframe(df_export, width="stretch", hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
            
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
                        if c_edit.button(":material/edit: Editar", width="stretch"):
                            st.session_state.edit_id = id_sel; st.session_state.edit_type = "forn"; st.session_state.form_key += 1; st.rerun()
                        if c_del.button(":material/delete: Apagar", width="stretch"):
                            f_nome = forn_obj.nome
                            session.query(Contrato).filter_by(fornecedor_id=id_sel).delete()
                            session.delete(forn_obj); session.commit()
                            registar_auditoria("APAGAR", "Fornecedores", f"Removeu o fornecedor '{f_nome}' e os respetivos contratos.")
                            st.session_state.toast = ("Contacto apagado!", "🗑️"); st.rerun()
        else: st.info("Ainda não existem fornecedores registados.")

    # ==========================================
    # TAB 2: CONTRATOS DE MANUTENÇÃO
    # ==========================================
    with tab_contratos:
        if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
            with st.expander(":material/post_add: Adicionar Novo Contrato"):
                fornecedores_ativos = session.query(Fornecedor).all()
                if not fornecedores_ativos:
                    st.warning("Tem de adicionar um Fornecedor antes de criar contratos.")
                else:
                    with st.form("form_contrato"):
                        opcoes_forn = {f"{f.nome} ({f.categoria})": f.id for f in fornecedores_ativos}
                        forn_selecionado = st.selectbox("Fornecedor Associado *", list(opcoes_forn.keys()))
                        titulo_contrato = st.text_input("Título / Referência do Contrato *")
                        
                        c_datas1, c_datas2 = st.columns(2)
                        with c_datas1: d_inicio = st.date_input("Data de Início", value=hoje)
                        with c_datas2: d_fim = st.date_input("Data de Fim (Expiração) *", value=hoje)
                        
                        valor_anual = st.number_input("Valor Anual (€)", min_value=0.0, format="%.2f")
                        
                        if st.form_submit_button("Guardar Contrato"):
                            if not titulo_contrato.strip():
                                st.error("O título do contrato é obrigatório.")
                            elif d_fim <= d_inicio:
                                st.error("A Data de Fim tem de ser posterior à Data de Início.")
                            else:
                                id_f = opcoes_forn[forn_selecionado]
                                novo_contrato = Contrato(fornecedor_id=id_f, titulo=titulo_contrato, data_inicio=d_inicio.strftime("%Y-%m-%d"), data_fim=d_fim.strftime("%Y-%m-%d"), valor_anual=valor_anual)
                                session.add(novo_contrato)
                                session.commit()
                                registar_auditoria("CRIAR", "Contratos", f"Registou um novo contrato '{titulo_contrato}'.")
                                st.session_state.toast = ("Contrato registado!", "✅")
                                st.rerun()

        contratos = session.query(Contrato).order_by(Contrato.data_fim.asc()).all()
        if contratos:
            st.write("Lista de contratos ativos e as suas datas de expiração.")
            with st.container(border=True):
                lista_tabela = []
                for c in contratos:
                    try:
                        dias = (datetime.strptime(c.data_fim, "%Y-%m-%d").date() - hoje).days
                        if dias < 0: estado = "🔴 Expirado"
                        elif dias <= 30: estado = "🟡 Expira Brevemente"
                        else: estado = "🟢 Ativo"
                    except: estado = "⚪ Desconhecido"
                    
                    lista_tabela.append({
                        "ID": c.id, "Estado": estado, "Fornecedor": c.fornecedor.nome if c.fornecedor else "N/D", 
                        "Título": c.titulo, "Expira a": c.data_fim, "Valor Anual": c.valor_anual
                    })
                    
                df_contratos = pd.DataFrame(lista_tabela)
                ev_contrato = st.dataframe(df_contratos, width="stretch", hide_index=True, column_config={"ID": None, "Valor Anual": st.column_config.NumberColumn("Valor (€)", format="%.2f €")}, on_select="rerun", selection_mode="single-row")
            
            if ev_contrato.selection.rows and st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.container(border=True):
                    id_c = int(df_contratos.iloc[ev_contrato.selection.rows[0]]["ID"])
                    c_obj = session.get(Contrato, id_c)
                    c_txt, c_btn = st.columns([4, 1])
                    c_txt.info(f"Selecionado: **{c_obj.titulo}** (Expira: {c_obj.data_fim})")
                    if c_btn.button("🗑️ Apagar Contrato", width="stretch"):
                        c_tit = c_obj.titulo
                        session.delete(c_obj); session.commit()
                        registar_auditoria("APAGAR", "Contratos", f"Apagou o registo do contrato '{c_tit}'.")
                        st.rerun()
        else: st.info("Não existem contratos de momento.")

def pagina_ocorrencias():
    import time
    from datetime import datetime
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    
    st.header(":material/build: Operações e Manutenção")
    
    tab_ocorrencias, tab_manutencao = st.tabs(["🛠️ Ocorrências Reportadas", "📅 Manutenção Preventiva"])
    
    # ==========================================
    # TAB 1: OCORRÊNCIAS REPORTADAS (Reativo)
    # ==========================================
    with tab_ocorrencias:
        # --- NOVO: Filtro Contextual Inteligente na Sidebar ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("🛠️ Estado da Ocorrência")
        filtro_oc = st.sidebar.radio(
            "Visualizar:",
            ["Todas", "🔴 Pendentes", "✅ Resolvidas"],
            key=f"sidebar_filter_oc_{st.session_state.form_key}"
        )

        if not st.session_state.modo_leitura:
            with st.expander(":material/add_alert: Registar Nova Ocorrência"):
                with st.form("f_oc"):
                    st.text_input("Reportado por", value=st.session_state.username, disabled=True)
                    tit = st.text_input("Assunto (ex: Fuga de água, Lâmpada fundida) *", key=f"o_tit_{st.session_state.form_key}")
                    desc = st.text_area("Descrição detalhada do problema *", key=f"o_desc_{st.session_state.form_key}")
                    
                    st.write("**Provas Fotográficas (Opcional)**")
                    c1, c2 = st.columns(2)
                    with c1: foto1 = st.file_uploader("Fotografia 1", type=["jpg", "jpeg", "png"], key=f"o_f1_{st.session_state.form_key}")
                    with c2: foto2 = st.file_uploader("Fotografia 2", type=["jpg", "jpeg", "png"], key=f"o_f2_{st.session_state.form_key}")
                    
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

                            session.add(Ocorrencia(titulo=tit, descricao=desc, data_criacao=hoje.strftime("%Y-%m-%d"), criado_por=st.session_state.username, foto1=caminho_f1, foto2=caminho_f2))
                            session.commit()
                            registar_auditoria("CRIAR", "Ocorrências", f"Abriu uma nova ocorrência técnica: '{tit}'.")
                            st.session_state.toast = ("Ocorrência registada com sucesso!", "✅")
                            st.session_state.form_key += 1; st.rerun()

        query_ocs = session.query(Ocorrencia).filter(and_(Ocorrencia.data_criacao >= str_inicio, Ocorrencia.data_criacao < str_fim))
        
        # Aplica o filtro da barra lateral dinamicamente à query SQL
        if "Pendentes" in filtro_oc:
            query_ocs = query_ocs.filter(Ocorrencia.resolvida == False)
        elif "Resolvidas" in filtro_oc:
            query_ocs = query_ocs.filter(Ocorrencia.resolvida == True)
            
        ocs = query_ocs.all()
        
        if ocs:
            with st.container(border=True):
                df_ocs = pd.DataFrame([{"ID": o.id, "Data": o.data_criacao, "Utilizador": o.criado_por if o.criado_por else "N/D", "Estado": "✅ Resolvido" if o.resolvida else "🔴 Pendente", "Assunto": o.titulo} for o in ocs])
                evento_oc = st.dataframe(df_ocs, width="stretch", hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
            
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
                        if col_estado.button(":material/lock_open: Reabrir" if oc_obj.resolvida else ":material/check_circle: Resolver", width="stretch"):
                            oc_obj.resolvida = not oc_obj.resolvida
                            session.commit()
                            est_txt = "RESOLVIDA" if oc_obj.resolvida else "REABERTA"
                            registar_auditoria("ATUALIZAR", "Ocorrências", f"Alterou o estado da ocorrência ID {oc_obj.id} ('{oc_obj.titulo}') para {est_txt}.")
                            st.rerun()
                        if col_del.button(":material/delete: Apagar", width="stretch"):
                            oc_tit = oc_obj.titulo
                            session.delete(oc_obj); session.commit()
                            registar_auditoria("APAGAR", "Ocorrências", f"Apagou o registo da ocorrência '{oc_tit}'.")
                            st.session_state.toast = ("Ocorrência apagada!", "🗑️"); st.rerun()
        else: st.info("Nenhuma ocorrência encontrada com o filtro atual.")

    # ==========================================
    # TAB 2: MANUTENÇÃO PREVENTIVA (Proativo)
    # ==========================================
    with tab_manutencao:
        st.write("Agende e acompanhe inspeções obrigatórias e manutenções regulares (Elevadores, Extintores, Limpeza de Caleiras, etc).")
        
        if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
            with st.expander(":material/calendar_add_on: Agendar Nova Intervenção"):
                fornecedores_ativos = session.query(Fornecedor).all()
                
                with st.form("form_intervencao"):
                    tit_int = st.text_input("Ação de Manutenção (ex: Inspeção Anual Extintores) *")
                    
                    c_form1, c_form2 = st.columns(2)
                    with c_form1:
                        data_int = st.date_input("Data Prevista / Agendada *", value=hoje)
                    with c_form2:
                        opcoes_forn = {"Nenhum / Interno": None}
                        if fornecedores_ativos:
                            for f in fornecedores_ativos: opcoes_forn[f"{f.nome} ({f.categoria})"] = f.id
                        forn_selecionado = st.selectbox("Fornecedor / Entidade", list(opcoes_forn.keys()))
                    
                    obs_int = st.text_area("Observações / Detalhes")
                    
                    if st.form_submit_button("Registar Agendamento"):
                        if not tit_int.strip():
                            st.error("O preenchimento da Ação de Manutenção é obrigatório.")
                        else:
                            id_forn = opcoes_forn[forn_selecionado]
                            nova_int = Intervencao(titulo=tit_int, data_agendada=data_int.strftime("%Y-%m-%d"), fornecedor_id=id_forn, observacoes=obs_int, concluida=False)
                            session.add(nova_int)
                            session.commit()
                            registar_auditoria("CRIAR", "Manutenção", f"Agendou a manutenção '{tit_int}' para {data_int.strftime('%d/%m/%Y')}.")
                            st.session_state.toast = ("Intervenção agendada!", "✅")
                            st.rerun()
                            
        intervencoes = session.query(Intervencao).order_by(Intervencao.data_agendada.asc()).all()
        if intervencoes:
            with st.container(border=True):
                lista_ints = []
                for i in intervencoes:
                    # Cálculo simples para alertas visuais na tabela
                    try:
                        dias = (datetime.strptime(i.data_agendada, "%Y-%m-%d").date() - hoje).days
                        if i.concluida: estado_txt = "✅ Concluída"
                        elif dias < 0: estado_txt = "🔴 Em Atraso"
                        elif dias <= 15: estado_txt = "🟡 Próxima"
                        else: estado_txt = "⏳ Agendada"
                    except: estado_txt = "⚪ Desconhecido"
                    
                    lista_ints.append({
                        "ID": i.id,
                        "Status": estado_txt,
                        "Data Prevista": i.data_agendada,
                        "Ação": i.titulo,
                        "Entidade": i.fornecedor.nome if i.fornecedor else "Interno"
                    })
                    
                df_ints = pd.DataFrame(lista_ints)
                ev_ints = st.dataframe(df_ints, width="stretch", hide_index=True, column_config={"ID": None}, on_select="rerun", selection_mode="single-row")
                
            if ev_ints.selection.rows and st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.container(border=True):
                    id_int = int(df_ints.iloc[ev_ints.selection.rows[0]]["ID"])
                    i_obj = session.get(Intervencao, id_int)
                    
                    c_txt, c_btn1, c_btn2 = st.columns([3, 1, 1])
                    c_txt.info(f"**Detalhes:** {i_obj.observacoes if i_obj.observacoes else 'Sem notas adicionais.'}")
                    
                    if c_btn1.button("Reabrir" if i_obj.concluida else "✔️ Dar como Concluída", width="stretch"):
                        i_obj.concluida = not i_obj.concluida
                        session.commit()
                        txt_aud = "CONCLUÍDA" if i_obj.concluida else "PENDENTE"
                        registar_auditoria("ATUALIZAR", "Manutenção", f"Marcou a intervenção '{i_obj.titulo}' como {txt_aud}.")
                        st.rerun()
                        
                    if c_btn2.button("🗑️ Apagar", width="stretch"):
                        i_tit = i_obj.titulo
                        session.delete(i_obj); session.commit()
                        registar_auditoria("APAGAR", "Manutenção", f"Removeu o agendamento de '{i_tit}'.")
                        st.rerun()
        else:
            st.info("Não existem manutenções preventivas agendadas de momento.")

def pagina_assembleias():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/diversity_3: Assembleias e Votações")
    tab_reunioes, tab_votos = st.tabs(["📅 Reuniões de Condomínio", "📊 Votações & Sondagens"])
    
    with tab_reunioes:
        if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
            with st.expander(":material/add_alert: Agendar Nova Assembleia"):
                with st.form("f_ass"):
                    tit = st.text_input("Título *", key=f"a_t_{st.session_state.form_key}")
                    data_reuniao = st.date_input("Data da Reunião", key=f"a_d_{st.session_state.form_key}")
                    assuntos = st.text_area("Ordem de Trabalhos (Assuntos) *", key=f"a_a_{st.session_state.form_key}")
                    enviar_email_convocatoria = st.checkbox("Enviar convocatória por email a todos", value=True, key=f"a_e_{st.session_state.form_key}")
                    
                    if st.form_submit_button("Agendar"):
                        if not tit.strip() or not assuntos.strip(): st.error("⚠️ Título e Ordem de Trabalhos obrigatórios.")
                        else:
                            session.add(Assembleia(titulo=tit, data_agendada=data_reuniao.strftime("%Y-%m-%d"), assuntos=assuntos))
                            session.commit()
                            registar_auditoria("CRIAR", "Assembleias", f"Agendou uma nova assembleia: '{tit}' para {data_reuniao.strftime('%d/%m/%Y')}.")
                            if enviar_email_convocatoria:
                                condominos_com_email = session.query(Condomino).filter(Condomino.email.isnot(None), Condomino.email != "").all()
                                emails_enviados = 0
                                for c in condominos_com_email:
                                    corpo = f"Exmo(a) Sr(a) {c.nome},\n\nConvocatória para a reunião de condomínio: {tit}.\nData: {data_reuniao.strftime('%d/%m/%Y')}\n\nAssuntos:\n{assuntos}\n\nAdministração."
                                    if enviar_email_real(c.email, f"Convocatória - {tit}", corpo): emails_enviados += 1
                                st.session_state.toast = (f"Assembleia agendada! {emails_enviados} convites enviados.", "✅")
                            else: st.session_state.toast = ("Assembleia agendada!", "✅")
                            st.session_state.form_key += 1; st.rerun()

        reunioes = session.query(Assembleia).order_by(Assembleia.id.desc()).all()
        if reunioes:
            for r in reunioes:
                with st.container(border=True):
                    col_txt, col_act = st.columns([4, 1])
                    estado = "✅ Realizada" if r.realizada else "⏳ Agendada"
                    col_txt.markdown(f"### {r.titulo} ({estado})")
                    col_txt.write(f"**Data:** {r.data_agendada} | **Ordem de Trabalhos:** {r.assuntos}")
                    
                    if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
                        if not r.realizada:
                            if col_act.button("Marcar como Realizada", key=f"real_{r.id}", width="stretch"): 
                                r.realizada = True; session.commit()
                                registar_auditoria("ATUALIZAR", "Assembleias", f"Fechou a assembleia '{r.titulo}' como REALIZADA.")
                                st.rerun()
                        else:
                            if col_act.button("Reabrir", key=f"undo_{r.id}", width="stretch"): 
                                r.realizada = False; session.commit()
                                registar_auditoria("ATUALIZAR", "Assembleias", f"Reabriu a assembleia concluída '{r.titulo}'.")
                                st.rerun()
                        if col_act.button("🗑️ Eliminar", key=f"del_ass_{r.id}", width="stretch"): 
                            a_tit = r.titulo
                            session.delete(r); session.commit()
                            registar_auditoria("APAGAR", "Assembleias", f"Eliminou a assembleia agendada '{a_tit}'.")
                            st.rerun()
                            
                    if r.realizada:
                        if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
                            with st.expander("📝 Redigir / Exportar Ata Digital", expanded=False):
                                
                                # --- MODELO DINÂMICO DE ATA ---
                                morada_cond = config.get("MORADA_CONDOMINIO", "[Morada do Condomínio]")
                                nif_cond = config.get("NIF_CONDOMINIO", "[NIF]")
                                
                                modelo_base = f"""ACTA Nº [Inserir Número da Ata]

Aos [Dia] dias do mês de [Mês] de [Ano] pelas [Hora] horas e [Minutos] minutos, reuniu no hall do prédio, a assembleia [ordinária / extraordinária] de condóminos do condomínio do edifício em propriedade horizontal sito em {morada_cond}, NIPC {nif_cond}, para deliberar sobre os seguintes assuntos:

{r.assuntos}

A assembleia foi regularmente convocada via [Carta / Email / WhatsApp] para conhecimento de todos os condóminos.

Estiveram presentes os seguintes condóminos:
- Proprietário da FRACÇÃO "[...]" representando uma permilagem de [...] do capital total do edifício.
- [Preencher restantes presentes...]

Não estiveram presentes os seguintes condóminos:
- Proprietário da FRACÇÃO "[...]" representando uma permilagem de [...] do capital total do edifício.
- [Preencher restantes ausentes...]

Exerceu as funções de presidente desta assembleia o(a) Sr(a). [Nome do Presidente] ----

Foram discutidos os assuntos da Ordem de Trabalhos, tendo-se deliberado o seguinte:

Relativamente ao primeiro ponto, [Escrever deliberação...]

No segundo ponto, [Escrever deliberação...]

Nada mais de relevante havendo a tratar, encerram-se os trabalhos da assembleia, lavrando-se a presente ata que, após lida e aprovada, vai ser assinada por mim, na qualidade de presidente desta assembleia e pelos condóminos presentes.

[Localidade], {r.data_agendada}.

O Presidente da Assembleia:
____________________________________________________

Os Condóminos:
Proprietário da FRACÇÃO "[...]": ______________________________________
Proprietário da FRACÇÃO "[...]": ______________________________________
"""
                                # Carrega o texto gravado ou o modelo base se estiver vazio
                                texto_atual = r.texto_ata if r.texto_ata else modelo_base
                                
                                # Aumentámos o height para 550 para ser mais confortável de editar textos longos
                                novo_texto = st.text_area("Corpo da Ata", value=texto_atual, height=550, key=f"ata_txt_{r.id}")
                                
                                if st.button("💾 Gravar Ata", key=f"save_{r.id}", type="primary"):
                                    r.texto_ata = novo_texto; session.commit()
                                    registar_auditoria("ATUALIZAR", "Assembleias", f"Redigiu/Atualizou a ata digital da assembleia '{r.titulo}'.")
                                    st.toast("Gravado com sucesso!", icon="✅")
                                
                                if r.texto_ata and REPORTLAB_INSTALLED:
                                    pdf_ata = gerar_pdf_ata(r)
                                    nome_ficheiro = f"Ata_{r.data_agendada}_{r.id}.pdf"
                                    
                                    c_d, c_a, c_m = st.columns(3)
                                    c_d.download_button("📥 Baixar PDF", data=pdf_ata, file_name=nome_ficheiro, mime="application/pdf")
                                    if c_a.button("🗂️ Arquivar no Portal", key=f"arq_{r.id}"):
                                        if not os.path.exists("uploads"): os.makedirs("uploads")
                                        caminho = os.path.join("uploads", nome_ficheiro)
                                        with open(caminho, "wb") as f: f.write(pdf_ata)
                                        if not session.query(Documento).filter_by(nome_ficheiro=nome_ficheiro).first():
                                            session.add(Documento(nome_ficheiro=nome_ficheiro, categoria="Atas de Assembleia", caminho=caminho, carregado_por="Sistema"))
                                            session.commit()
                                            registar_auditoria("CRIAR", "Arquivo", f"Arquivou a ata em PDF da assembleia '{r.titulo}'.")
                                            st.success("Ata arquivada com sucesso nos Documentos!")
                                    if c_m.button("📧 Enviar por Email", key=f"mail_{r.id}"):
                                        with st.spinner("A enviar emails com a ata..."):
                                            conds_email = session.query(Condomino).filter(Condomino.email.isnot(None), Condomino.email != "").all()
                                            enviados = 0
                                            for c in conds_email:
                                                if enviar_email_real(c.email, f"Ata de Assembleia - {r.titulo}", "Estimado(a) Condómino(a),\n\nSegue em anexo a ata da reunião.\n\nA Administração.", anexo_bytes=pdf_ata, nome_anexo=nome_ficheiro): enviados += 1
                                            st.success(f"Ata enviada para {enviados} proprietários!")
                        else:
                            if r.texto_ata:
                                with st.expander("👁️ Visualizar Ata"):
                                    st.write(r.texto_ata)
                                    if REPORTLAB_INSTALLED:
                                        st.download_button("📥 Descarregar PDF da Ata", data=gerar_pdf_ata(r), file_name=f"Ata_{r.data_agendada}.pdf")

    with tab_votos:
        if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
            with st.expander(":material/poll: Criar Nova Sondagem"):
                with st.form("f_sond"):
                    perg = st.text_input("Pergunta / Assunto a Votar *")
                    opcoes_str = st.text_input("Opções (separadas por vírgula) *", value="Favor, Contra, Abstenção")
                    if st.form_submit_button("Criar Votação"):
                        if not perg.strip() or not opcoes_str.strip(): st.error("Campos obrigatórios.")
                        else:
                            session.add(Sondagem(pergunta=perg, opcoes=opcoes_str))
                            session.commit()
                            registar_auditoria("CRIAR", "Votações", f"Criou uma nova sondagem/votação: '{perg}'.")
                            st.session_state.form_key += 1; st.rerun()

        sondagens = session.query(Sondagem).order_by(Sondagem.id.desc()).all()
        if sondagens:
            for s in sondagens:
                with st.container(border=True):
                    st.markdown(f"#### ❓ {s.pergunta}")
                    status = "🟢 ATIVA" if s.ativa else "🔴 ENCERRADA"
                    st.caption(f"Status: {status} | Criada em: {s.data_criacao}")
                    
                    lista_opcoes = [op.strip() for op in s.opcoes.split(",")] if s.opcoes else ["Favor", "Contra", "Abstenção"]
                    resultados = []
                    for op in lista_opcoes:
                        votos_op = session.query(VotoSondagem).filter_by(sondagem_id=s.id, resposta=op).count()
                        resultados.append(f"**{op}:** {votos_op}")
                    st.write(" | ".join(resultados))
                    
                    if s.ativa and st.session_state.perfil == "Morador":
                        ja_votou = session.query(VotoSondagem).filter_by(sondagem_id=s.id, condomino_id=st.session_state.condomino_id).first()
                        if ja_votou: st.success(f"Voto registado: {ja_votou.resposta}")
                        else:
                            with st.form(f"form_voto_{s.id}"):
                                escolha = st.radio("Sua resposta:", lista_opcoes)
                                if st.form_submit_button("Votar"):
                                    session.add(VotoSondagem(sondagem_id=s.id, condomino_id=st.session_state.condomino_id, resposta=escolha))
                                    session.commit()
                                    registar_auditoria("CRIAR", "Votações", f"Morador votou '{escolha}' na sondagem ID {s.id}.")
                                    st.rerun()

                    if st.session_state.perfil == "Admin":
                        c_act1, c_act2 = st.columns(2)
                        if c_act1.button("Abrir/Fechar", key=f"alt_{s.id}"): 
                            s.ativa = not s.ativa; session.commit()
                            est_v = "ATIVOU" if s.ativa else "ENCERROU"
                            registar_auditoria("ATUALIZAR", "Votações", f"{est_v} a sondagem ID {s.id} ('{s.pergunta}').")
                            st.rerun()
                        if c_act2.button("Apagar Votação", key=f"del_s_{s.id}"):
                            s_perg = s.pergunta
                            session.query(VotoSondagem).filter_by(sondagem_id=s.id).delete()
                            session.delete(s); session.commit()
                            registar_auditoria("APAGAR", "Votações", f"Apagou permanentemente a sondagem '{s_perg}' e todos os seus votos.")
                            st.rerun()
        else: st.info("Não existem votações de momento.")

def pagina_mural():
    from datetime import datetime
    st.header(":material/forum: Mural da Comunidade")
    st.write("Um espaço para partilhar anúncios, pedidos ou comunicados com os seus vizinhos.")
    
    if not st.session_state.modo_leitura:
        with st.expander(":material/add_comment: Criar Novo Anúncio", expanded=False):
            with st.form("form_anuncio"):
                titulo = st.text_input("Título (ex: Obras no 2º Andar, Preciso de Ferramenta, etc)")
                mensagem = st.text_area("Mensagem")
                
                if st.form_submit_button("Publicar no Mural"):
                    if not titulo.strip() or not mensagem.strip():
                        st.error("O título e a mensagem são obrigatórios.")
                    else:
                        fracao_str = "Admin" if st.session_state.perfil == "Admin" else ""
                        if st.session_state.condomino_id:
                            cond = session.get(Condomino, st.session_state.condomino_id)
                            if cond: fracao_str = f"Fr. {cond.fracao}"
                        
                        session.add(Anuncio(titulo=titulo, mensagem=mensagem, data_criacao=datetime.now().strftime("%Y-%m-%d %H:%M"), criado_por=st.session_state.username, fracao=fracao_str))
                        session.commit()
                        registar_auditoria("CRIAR", "Mural", f"Publicou no mural comunitário: '{titulo}'.")
                        st.session_state.toast = ("Anúncio publicado com sucesso!", "✅")
                        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    anuncios = session.query(Anuncio).order_by(Anuncio.id.desc()).all()
    if anuncios:
        for a in anuncios:
            with st.container(border=True):
                c_post, c_del = st.columns([5, 1])
                c_post.markdown(f"#### {a.titulo}")
                c_post.caption(f"👤 Publicado por **{a.criado_por}** ({a.fracao}) em {a.data_criacao}")
                c_post.write(a.mensagem)
                
                if not st.session_state.modo_leitura:
                    pode_apagar = (st.session_state.perfil == "Admin") or (a.criado_por == st.session_state.username)
                    if pode_apagar:
                        if c_del.button("🗑️ Apagar", key=f"del_an_{a.id}", use_container_width=True):
                            a_tit = a.titulo
                            session.delete(a); session.commit()
                            registar_auditoria("APAGAR", "Mural", f"Apagou o anúncio do mural: '{a_tit}'.")
                            st.rerun()
    else: st.info("O mural está silencioso. Seja o primeiro a publicar algo!")

# --- HELPER FUNCTIONS PARA DUMP COMPLETO JSON ---
def gerar_snapshot_json():
    db_dump = {}
    models_to_export = {
        "condominos": Condomino, "utilizadores": Utilizador, "orcamentos": Orcamento,
        "movimentos": Movimento, "quotas": Quota, "ocorrencias": Ocorrencia, "intervencoes": Intervencao, 
        "documentos": Documento, "fornecedores": Fornecedor, "contratos": Contrato,
        "assembleias": Assembleia, "sondagens": Sondagem, "votos_sondagem": VotoSondagem, 
        "anuncios": Anuncio, "auditoria": Auditoria
    }
    for key, model in models_to_export.items():
        rows = session.query(model).all()
        list_rows = []
        for r in rows:
            d = {col.name: getattr(r, col.name) for col in r.__table__.columns}
            list_rows.append(d)
        db_dump[key] = list_rows
    return json.dumps(db_dump, indent=4, ensure_ascii=False)

def restaurar_snapshot_json(json_str):
    try:
        data = json.loads(json_str)
        session.rollback()
        
        # 1. Limpar Tudo (Reset Suave Prévio)
        session.query(VotoSondagem).delete()
        session.query(Sondagem).delete()
        session.query(Anuncio).delete()
        session.query(Assembleia).delete()
        session.query(Ocorrencia).delete()
        session.query(Intervencao).delete()
        session.query(Contrato).delete()
        session.query(Fornecedor).delete()
        session.query(Documento).delete()
        session.query(Movimento).delete()
        session.query(Orcamento).delete()
        session.query(Quota).delete()
        session.query(Utilizador).delete()
        session.query(Condomino).delete()
        session.query(Auditoria).delete()
        session.commit()
        
        # 2. Injeção Ordenada Estrita
        if "condominos" in data:
            for r in data["condominos"]: session.add(Condomino(**r))
            session.commit()
            
        tabelas_fase2 = {
            "utilizadores": Utilizador, "orcamentos": Orcamento, "movimentos": Movimento,
            "quotas": Quota, "ocorrencias": Ocorrencia, "documentos": Documento,
            "fornecedores": Fornecedor, "contratos": Contrato, "assembleias": Assembleia, "sondagens": Sondagem, "intervencoes": Intervencao
        }
        for key, model in tabelas_fase2.items():
            if key in data:
                for r in data[key]: session.add(model(**r))
        session.commit()
        
        if "votos_sondagem" in data:
            for r in data["votos_sondagem"]: session.add(VotoSondagem(**r))
        if "anuncios" in data:
            for r in data["anuncios"]: session.add(Anuncio(**r))
        if "auditoria" in data:
            for r in data["auditoria"]: session.add(Auditoria(**r))
        session.commit()
        
        # 3. Sincronizar Sequências do PostgreSQL
        if engine.name == 'postgresql':
            from sqlalchemy import text
            tabelas_seq = ['votos_sondagem', 'sondagens', 'anuncios', 'assembleias', 'ocorrencias', 'contratos', 'fornecedores', 'documentos', 'movimentos', 'orcamentos', 'quotas', 'utilizadores', 'condominos', 'auditoria', 'intervencoes']
            for tabela in tabelas_seq:
                try:
                    max_id = session.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {tabela};")).scalar()
                    session.execute(text(f"ALTER SEQUENCE {tabela}_id_seq RESTART WITH {max_id + 1};"))
                except Exception: session.rollback()
            session.commit()
            
        return True, "Base de dados restaurada com sucesso a partir da Segurança"
    except Exception as e:
        session.rollback()
        return False, f"Falha no restauro da Segurança. Detalhe: {str(e)}"

def pagina_configuracoes():
    mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()
    st.header(":material/settings: Configurações e Segurança")
    
    if not st.session_state.modo_leitura:
        tab_geral, tab_avisos, tab_seguranca, tab_auditoria = st.tabs([
            ":material/business: Dados Gerais", 
            ":material/campaign: Quadro de Avisos", 
            ":material/security: Backup & Reset BD",
            ":material/history: Logs de Auditoria"
        ])
        
        with tab_geral:
            with st.container(border=True):
                with st.form("form_config"):
                    st.subheader("Configurações do Condomínio")
                    nome = st.text_input("Nome do Condomínio", value=config.get("NOME_CONDOMINIO", ""), key=f"cfg_n_{st.session_state.form_key}")
                    titulo_log = st.text_input("Título no Ecrã de Login", value=config.get("TITULO_LOGIN", "A3® Portal do Condomínio"), key=f"cfg_tl_{st.session_state.form_key}")
                    morada = st.text_input("Morada", value=config.get("MORADA_CONDOMINIO", ""), key=f"cfg_m_{st.session_state.form_key}")
                    nif = st.text_input("NIF", value=config.get("NIF_CONDOMINIO", ""), key=f"cfg_nif_{st.session_state.form_key}")
                    iban = st.text_input("IBAN para Pagamentos", value=config.get("IBAN_CONDOMINIO", ""), key=f"cfg_ib_{st.session_state.form_key}")
                    valor_quota = st.number_input("Valor Padrão da Quota (€)", value=config.get("VALOR_MENSAL_FIXO", 50.0), min_value=0.0, key=f"cfg_v_{st.session_state.form_key}")
                    
                    if st.form_submit_button("Guardar Configurações"):
                        config["NOME_CONDOMINIO"] = nome
                        config["TITULO_LOGIN"] = titulo_log
                        config["MORADA_CONDOMINIO"] = morada
                        config["NIF_CONDOMINIO"] = nif
                        config["IBAN_CONDOMINIO"] = iban
                        config["VALOR_MENSAL_FIXO"] = valor_quota
                        guardar_configs(config)
                        registar_auditoria("ATUALIZAR", "Configurações", "Atualizou as informações administrativas basilares e identidade visual do login.")
                        st.session_state.toast = ("Configurações atualizadas!", "✅")
                        st.session_state.form_key += 1; st.rerun()
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- PAINEL DE BRANDING COM RESET REAL DE COMPONENTES ---
            with st.container(border=True):
                st.subheader("🎨 Identidade Visual & Branding")
                st.write("Faça a gestão das imagens de marca do portal de condomínio.")
                
                c_logo, c_bg = st.columns(2)
                
                with c_logo:
                    st.markdown("**Logótipo Principal (`logo.png`)**")
                    if os.path.exists("logo.png"):
                        st.image("logo.png", width=120)
                        # Botão para apagar o logótipo
                        if st.button("❌ Remover Logótipo Atual", key="btn_clear_logo", width="stretch"):
                            os.remove("logo.png")
                            registar_auditoria("APAGAR", "Configurações", "Removeu o logótipo oficial do sistema.")
                            st.rerun()
                    else:
                        st.caption("ℹ️ Nenhum logótipo configurado (ecrã em modo simples).")
                        
                    # Mudança crítica: key agora é dinâmica com o form_key
                    up_logo = st.file_uploader("Carregar novo logótipo", type=["png", "jpg", "jpeg"], key=f"cfg_up_logo_{st.session_state.form_key}")
                    if up_logo is not None:
                        if st.button("Aplicar Novo Logótipo", width="stretch", type="primary"):
                            with open("logo.png", "wb") as f:
                                f.write(up_logo.getbuffer())
                            registar_auditoria("ATUALIZAR", "Configurações", "Alterou o logótipo oficial do sistema.")
                            
                            # Força a destruição do widget antigo incrementando o form_key
                            st.session_state.form_key += 1
                            st.rerun()
                            
                with c_bg:
                    st.markdown("**Imagem do Fundo de Login (`bg_login.png`)**")
                    if os.path.exists("bg_login.png"):
                        st.image("bg_login.png", width=180)
                        # Botão para apagar o fundo de login
                        if st.button("❌ Remover Fundo de Login", key="btn_clear_bg", width="stretch"):
                            os.remove("bg_login.png")
                            registar_auditoria("APAGAR", "Configurações", "Removeu a imagem de fundo do login.")
                            st.rerun()
                    else:
                        st.caption("ℹ️ Nenhuma imagem de fundo configurada (ecrã em modo simples).")
                        
                    # Mudança crítica: key agora é dinâmica com o form_key
                    up_bg = st.file_uploader("Carregar nova imagem de login", type=["png", "jpg", "jpeg"], key=f"cfg_up_bg_{st.session_state.form_key}")
                    if up_bg is not None:
                        if st.button("Aplicar Novo Fundo de Login", width="stretch", type="primary"):
                            with open("bg_login.png", "wb") as f:
                                f.write(up_bg.getbuffer())
                            registar_auditoria("ATUALIZAR", "Configurações", "Alterou a imagem de fundo do ecrã de login.")
                            
                            # Força a destruição do widget antigo incrementando o form_key
                            st.session_state.form_key += 1
                            st.rerun()
                        
        with tab_avisos:
            with st.container(border=True):
                with st.form("form_avisos"):
                    st.subheader("Avisos à Comunidade")
                    aviso_ativo = st.checkbox("Mostrar aviso publicamente", value=config.get("AVISO_ATIVO", False), key=f"cfg_av_at_{st.session_state.form_key}")
                    aviso_texto = st.text_area("Texto do Aviso", value=config.get("AVISO_GLOBAL", ""), key=f"cfg_av_txt_{st.session_state.form_key}")
                    
                    if st.form_submit_button("Atualizar Quadro de Avisos"):
                        config["AVISO_ATIVO"] = aviso_ativo
                        config["AVISO_GLOBAL"] = aviso_texto
                        guardar_configs(config)
                        registar_auditoria("ATUALIZAR", "Configurações", "Atualizou o quadro de avisos globais no ecrã principal dos moradores.")
                        st.session_state.toast = ("Aviso atualizado com sucesso!", "✅")
                        st.session_state.form_key += 1; st.rerun()
                        
        with tab_seguranca:
            with st.container(border=True):
                st.subheader("📦 Segurança Completa da Base de Dados")
                st.write("Processo de Exportação e Importação da Base de Dados num unico ficheiro.")
                
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
                    arq_import_json = st.file_uploader("Importar Ficheiro .json", type=["json"], key=f"upload_snapshot_json")
                    if arq_import_json is not None:
                        if st.button("🔄 Executar Restauro da Segurança Agora", use_container_width=True, type="primary"):
                            with st.spinner("A restaurar o sistema da cópia de segurança..."):
                                conteudo_json_string = arq_import_json.read().decode("utf-8")
                                sucesso, msg_res = restaurar_snapshot_json(conteudo_json_string)
                                if sucesso:
                                    registar_auditoria("ATUALIZAR", "Sistema", "Executou uma restauração completa do ecossistema de BD a partir de ficheiro JSON.")
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
                    st.warning("Atenção: Esta operação apaga permanentemente todos os registos.")
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
                                    session.query(Intervencao).delete()
                                    session.query(Contrato).delete()
                                    session.query(Fornecedor).delete()
                                    session.query(Documento).delete()
                                    session.query(Movimento).delete()
                                    session.query(Orcamento).delete()
                                    session.query(Quota).delete()
                                    session.query(Utilizador).delete()
                                    session.query(Condomino).delete()
                                    session.query(Auditoria).delete()
                                    session.commit()
                                    
                                    if engine.name == "postgresql":
                                        tabelas = ["votos_sondagem", "sondagens", "anuncios", "assembleias", "ocorrencias", "contratos", "fornecedores", "documentos", "movimentos", "orcamentos", "quotas", "utilizadores", "condominos", "auditoria"]
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

        with tab_auditoria:
            st.subheader("📋 Rasto de Auditoria do Sistema")
            st.write("Exibição em tempo real das ações e eventos ocorridos na aplicação (limite circular de 200 registos históricos).")
            
            logs = session.query(Auditoria).order_by(Auditoria.id.desc()).all()
            if logs:
                df_logs = pd.DataFrame([{
                    "Data/Hora": log.data_hora,
                    "Utilizador": log.username,
                    "Ação": log.acao,
                    "Módulo/Área": log.entidade,
                    "Descrição do Evento": log.detalhes
                } for log in logs])
                
                st.dataframe(df_logs, use_container_width=True, hide_index=True)
            else:
                st.info("Ainda não existem registos de auditoria registados no sistema.")

# ==========================================
# MOTOR DE NAVEGAÇÃO E CONTROLO DE ACESSOS
# ==========================================
if not st.session_state.logado:
    pg = st.navigation([st.Page(pagina_login, title="Acesso Reservado", icon=":material/lock:")])
else:
    if st.session_state.perfil == "Admin":
        pg = st.navigation({
            "VISÃO GERAL": [
                st.Page(pagina_dashboard, title="Dashboard", icon=":material/dashboard:", default=True), 
                st.Page(pagina_condominos, title="Condóminos", icon=":material/group:")
            ],
            "TESOURARIA": [
                st.Page(pagina_quotas, title="Gestão de Quotas", icon=":material/payments:"), 
                st.Page(pagina_financas, title="Finanças & Extratos", icon=":material/account_balance:"), 
                st.Page(pagina_recibos, title="Emissão de Recibos", icon=":material/receipt_long:")
            ],
            "OPERAÇÕES & COMUNIDADE": [
                st.Page(pagina_mural, title="Mural da Comunidade", icon=":material/forum:"),
                st.Page(pagina_assembleias, title="Assembleias & Votações", icon=":material/diversity_3:"),
                st.Page(pagina_documentos, title="Arquivo Digital", icon=":material/folder_open:"),
                st.Page(pagina_fornecedores, title="Fornecedores e Contratos", icon=":material/contact_phone:"),
                st.Page(pagina_ocorrencias, title="Ocorrências", icon=":material/build:")
            ],
            "SISTEMA": [
                st.Page(pagina_acessos, title="Gestão de Acessos", icon=":material/admin_panel_settings:"),
                st.Page(pagina_configuracoes, title="Configurações", icon=":material/settings:")
            ]
        })
    else: 
        nav_morador = {
            "A MINHA CONTA": [
                st.Page(pagina_dashboard_morador, title="Conta Corrente", icon=":material/home:", default=True)
            ]
        }
        
        vg_pages = []
        if st.session_state.perm_dashboard: vg_pages.append(st.Page(pagina_dashboard, title="Dashboard", icon=":material/dashboard:"))
        if st.session_state.perm_condominos: vg_pages.append(st.Page(pagina_condominos, title="Condóminos", icon=":material/group:"))
        if vg_pages: nav_morador["DASHBOARD GLOBAL"] = vg_pages
        
        tes_pages = []
        if st.session_state.perm_quotas: tes_pages.append(st.Page(pagina_quotas, title="Gestão de Quotas", icon=":material/payments:"))
        if st.session_state.perm_financas: tes_pages.append(st.Page(pagina_financas, title="Finanças & Extratos", icon=":material/account_balance:"))
        if st.session_state.perm_recibos: tes_pages.append(st.Page(pagina_recibos, title="Emissão de Recibos", icon=":material/receipt_long:"))
        if tes_pages: nav_morador["TESOURARIA PÚBLICA"] = tes_pages
            
        op_pages = []
        if st.session_state.perm_mural: op_pages.append(st.Page(pagina_mural, title="Mural da Comunidade", icon=":material/forum:"))
        if st.session_state.perm_assembleias: op_pages.append(st.Page(pagina_assembleias, title="Assembleias & Votações", icon=":material/diversity_3:"))
        if st.session_state.perm_arquivo: op_pages.append(st.Page(pagina_documentos, title="Arquivo Digital", icon=":material/folder_open:"))
        if st.session_state.perm_fornecedores: op_pages.append(st.Page(pagina_fornecedores, title="Fornecedores", icon=":material/contact_phone:"))
        if st.session_state.perm_ocorrencias: op_pages.append(st.Page(pagina_ocorrencias, title="Ocorrências", icon=":material/build:"))
        if op_pages: nav_morador["CONDOMÍNIO"] = op_pages
            
        pg = st.navigation(nav_morador)

pg.run()
