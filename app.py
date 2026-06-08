import streamlit as st
print("ESTOU A ARRANCAR O APP.PY!")
from db import init_db, get_session
from models import Utilizador
from werkzeug.security import generate_password_hash

# 1. Configuração Global e Base de Dados
st.set_page_config(page_title="A3® Portal do Condomínio", page_icon="🏢", layout="wide")
init_db()
session = get_session()

# 2. Inicialização do Administrador e Estados Globais
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

# Inicializar dicionário st.session_state se necessário
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

# Gestor de Toasts (Notificações)
if "toast" in st.session_state:
    st.toast(st.session_state.toast[0], icon=st.session_state.toast[1])
    del st.session_state.toast

# 3. Estilos CSS Globais
st.markdown("""
<style>
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e2e8f0; padding: 5% 5% 5% 10%; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; background-color: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; padding: 8px; }
    div[data-testid="stAlert"] { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# 4. Roteamento de Páginas (st.navigation)
if not st.session_state.logado:
    pg = st.navigation([st.Page("views/login.py", title="Acesso Reservado", icon=":material/lock:")])
else:
    if st.session_state.perfil == "Admin":
        pg = st.navigation({
            "VISÃO GERAL": [
                st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True), 
                st.Page("views/condominos.py", title="Condóminos", icon=":material/group:")
            ],
            "TESOURARIA": [
                st.Page("views/quotas.py", title="Gestão de Quotas", icon=":material/payments:"), 
                st.Page("views/financas.py", title="Finanças & Extratos", icon=":material/account_balance:"), 
                st.Page("views/recibos.py", title="Emissão de Recibos", icon=":material/receipt_long:")
            ],
            "OPERAÇÕES & COMUNIDADE": [
                st.Page("views/mural.py", title="Mural da Comunidade", icon=":material/forum:"),
                st.Page("views/assembleias.py", title="Assembleias & Votações", icon=":material/diversity_3:"),
                st.Page("views/documentos.py", title="Arquivo Digital", icon=":material/folder_open:"),
                st.Page("views/fornecedores.py", title="Fornecedores", icon=":material/contact_phone:"),
                st.Page("views/ocorrencias.py", title="Ocorrências", icon=":material/build:")
            ],
            "SISTEMA": [
                st.Page("views/acessos.py", title="Gestão de Acessos", icon=":material/admin_panel_settings:"),
                st.Page("views/configuracoes.py", title="Configurações", icon=":material/settings:")
            ]
        })
    else: 
        nav_morador = {
            "A MINHA CONTA": [
                st.Page("views/dashboard_morador.py", title="Conta Corrente", icon=":material/home:", default=True)
            ]
        }
        
        vg_pages = []
        if st.session_state.perm_dashboard: vg_pages.append(st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:"))
        if st.session_state.perm_condominos: vg_pages.append(st.Page("views/condominos.py", title="Condóminos", icon=":material/group:"))
        if vg_pages: nav_morador["DASHBOARD GLOBAL"] = vg_pages
        
        tes_pages = []
        if st.session_state.perm_quotas: tes_pages.append(st.Page("views/quotas.py", title="Gestão de Quotas", icon=":material/payments:"))
        if st.session_state.perm_financas: tes_pages.append(st.Page("views/financas.py", title="Finanças & Extratos", icon=":material/account_balance:"))
        if st.session_state.perm_recibos: tes_pages.append(st.Page("views/recibos.py", title="Emissão de Recibos", icon=":material/receipt_long:"))
        if tes_pages: nav_morador["TESOURARIA PÚBLICA"] = tes_pages
            
        op_pages = []
        if st.session_state.perm_mural: op_pages.append(st.Page("views/mural.py", title="Mural da Comunidade", icon=":material/forum:"))
        if st.session_state.perm_assembleias: op_pages.append(st.Page("views/assembleias.py", title="Assembleias & Votações", icon=":material/diversity_3:"))
        if st.session_state.perm_arquivo: op_pages.append(st.Page("views/documentos.py", title="Arquivo Digital", icon=":material/folder_open:"))
        if st.session_state.perm_fornecedores: op_pages.append(st.Page("views/fornecedores.py", title="Fornecedores", icon=":material/contact_phone:"))
        if st.session_state.perm_ocorrencias: op_pages.append(st.Page("views/ocorrencias.py", title="Ocorrências", icon=":material/build:"))
        if op_pages: nav_morador["CONDOMÍNIO"] = op_pages
            
        pg = st.navigation(nav_morador)

pg.run()
