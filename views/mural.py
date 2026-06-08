import streamlit as st
from datetime import datetime

from db import get_session
from models import Anuncio, Condomino

session = get_session()

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
                    
                    session.add(Anuncio(
                        titulo=titulo, 
                        mensagem=mensagem, 
                        data_criacao=datetime.now().strftime("%Y-%m-%d %H:%M"), 
                        criado_por=st.session_state.username, 
                        fracao=fracao_str
                    ))
                    session.commit()
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
                        session.delete(a); session.commit(); st.rerun()
else: 
    st.info("O mural está silencioso. Seja o primeiro a publicar algo!")