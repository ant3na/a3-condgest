import streamlit as st
import pandas as pd
import os
import io
import json
import base64
import smtplib
import zipfile
import unicodedata
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import date
from datetime import datetime
from io import BytesIO
from sqlalchemy import func, and_, text

# Importações da Base de Dados
from models import Base, Condomino, Utilizador, Quota, Movimento, Ocorrencia, Orcamento, Documento, Fornecedor, Assembleia, Sondagem, VotoSondagem, Anuncio
from db import get_session, engine

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

# Inicialização de sessão global para os utilitários
session = get_session()

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
            
            # Linha horizontal minimalista de rodapé
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(50, 45, 545, 45)
            
            # Paginação dinâmica ("Página X de Y")
            texto_pagina = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(545, 30, texto_pagina)
            
            # Identificador institucional fixo
            self.drawString(50, 30, " A3® Portal do Condomínio")
            self.restoreState()

# ==========================================
# GESTÃO DE CONFIGURAÇÕES (JSON) E HELPERS
# ==========================================
CONFIG_FILE = "config.json"
caminho_logo = "logo.png"

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
    if len(partes) > 1:
        raw_user = f"{partes[0][0]}{partes[-1]}"
    else:
        raw_user = partes[0]
    raw_user = raw_user.lower()
    return "".join(c for c in unicodedata.normalize("NFD", raw_user) if unicodedata.category(c) != "Mn")

def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

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
# HELPER FUNCTIONS PARA DUMP COMPLETO JSON
# ==========================================
def gerar_snapshot_json():
    db_dump = {}
    models_to_export = {
        "condominos": Condomino, "utilizadores": Utilizador, "orcamentos": Orcamento,
        "movimentos": Movimento, "quotas": Quota, "ocorrencias": Ocorrencia,
        "documentos": Documento, "fornecedores": Fornecedor, "assembleias": Assembleia,
        "sondagens": Sondagem, "votos_sondagem": VotoSondagem, "anuncios": Anuncio
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
        
        # Limpar Tudo (Reset Suave Prévio)
        session.query(VotoSondagem).delete()
        session.query(Sondagem).delete()
        session.query(Anuncio).delete()
        session.query(Assembleia).delete()
        session.query(Ocorrencia).delete()
        session.query(Fornecedor).delete()
        session.query(Documento).delete()
        session.query(Movimento).delete()
        session.query(Orcamento).delete()
        session.query(Quota).delete()
        session.query(Utilizador).delete()
        session.query(Condomino).delete()
        session.commit()
        
        # Injeção Ordenada Estrita
        if "condominos" in data:
            for r in data["condominos"]: session.add(Condomino(**r))
            session.commit()
            
        tabelas_fase2 = {
            "utilizadores": Utilizador, "orcamentos": Orcamento, "movimentos": Movimento,
            "quotas": Quota, "ocorrencias": Ocorrencia, "documentos": Documento,
            "fornecedores": Fornecedor, "assembleias": Assembleia, "sondagens": Sondagem
        }
        for key, model in tabelas_fase2.items():
            if key in data:
                for r in data[key]: session.add(model(**r))
        session.commit()
        
        if "votos_sondagem" in data:
            for r in data["votos_sondagem"]: session.add(VotoSondagem(**r))
        if "anuncios" in data:
            for r in data["anuncios"]: session.add(Anuncio(**r))
        session.commit()
        
        # Sincronizar Sequências do PostgreSQL (apenas para DBs nativas em cloud)
        if engine.name == 'postgresql':
            tabelas_seq = ['votos_sondagem', 'sondagens', 'anuncios', 'assembleias', 'ocorrencias', 'fornecedores', 'documentos', 'movimentos', 'orcamentos', 'quotas', 'utilizadores', 'condominos']
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
    
# ==========================================
# BARRA LATERAL (LOGO E FILTROS)
# ==========================================
hoje = date.today()
meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

def configurar_sidebar():
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if os.path.exists("logo.png"):
        col1, col2, col3 = st.sidebar.columns([1, 2.5, 1])
        with col2: st.image("logo.png", use_container_width=True)
    st.sidebar.title(":material/corporate_fare: A3® Cond.Gest")
    st.sidebar.markdown("---")
    
    if st.session_state.logado:
        st.sidebar.write(f":material/account_circle: Olá, **{st.session_state.username}**")
        if st.session_state.modo_leitura:
            st.sidebar.caption(":material/visibility: MODO LEITURA")
        
        if st.sidebar.button(":material/logout: Terminar Sessão", use_container_width=True):
            st.session_state.logado = False
            st.session_state.username = None
            st.session_state.perfil = None
            st.session_state.condomino_id = None
            st.session_state.user_id = None
            st.session_state.modo_leitura = False
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
    st.sidebar.caption("💡 **Atenção:** Facilite a vida. Pague a tempo e a horas. > **Settings** > **Theme**.")
    
    return mes_sel, ano_sel, str_inicio, str_fim, mes_str

def gerar_backup_unificado_zip(session):
    """
    Segurança Completa: Dados + Ficheiros.
    """
    # 1. Criar um buffer em memória para o ficheiro ZIP (evita criar lixo no disco da VPS)
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        # --- FRENTE A: DUMP DA BASE DE DADOS (SUPABASE) ---
        # Lista de tabelas do teu sistema para backup
        tabelas = [
            "utilizadores", "condominos", "quotas", "movimentos", 
            "recibos", "assembleias", "documentos", "fornecedores", 
            "ocorrencias", "mural"
        ]
        
        dados_globais = {}
        
        for tabela in tabelas:
            try:
                # Executa uma query direta para extrair os dados de cada tabela
                result = session.execute(text(f"SELECT * FROM {tabela}"))
                colunas = result.keys()
                # Transforma as linhas em dicionários
                linhas = [dict(zip(colunas, row)) for row in result.fetchall()]
                
                # Trata formatos de data/hora e bytes para que o JSON não quebre
                for linha in linhas:
                    for k, v in linha.items():
                        if hasattr(v, "isoformat"):  # Converte datetime/date para texto
                            linha[k] = v.isoformat()
                        elif isinstance(v, bytes):
                            linha[k] = v.decode('utf-8', errors='ignore')
                            
                dados_globais[tabela] = linhas
            except Exception as e:
                # Se a tabela ainda não existir no teu banco, regista o aviso no JSON em vez de falhar
                dados_globais[tabela] = f"Aviso: {str(e)}"
        
        # Escreve o dump estruturado num ficheiro JSON dentro do arquivo ZIP
        json_data = json.dumps(dados_globais, indent=4, ensure_ascii=False)
        zip_file.writestr("database_dump.json", json_data)
        
        # --- FRENTE B: COPIAR FICHEIROS FÍSICOS (PASTA UPLOADS DA VPS) ---
        pasta_uploads = "uploads"
        if os.path.exists(pasta_uploads):
            for raiz, _, ficheiros in os.walk(pasta_uploads):
                for ficheiro in ficheiros:
                    caminho_completo = os.path.join(raiz, ficheiro)
                    # Calcula o caminho relativo para a estrutura de pastas dentro do ZIP ficar limpa
                    caminho_no_zip = os.path.relpath(caminho_completo, os.path.dirname(pasta_uploads))
                    zip_file.write(caminho_completo, caminho_no_zip)
                    
    # Reposiciona o ponteiro do buffer no início para o Streamlit conseguir fazer a leitura
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
