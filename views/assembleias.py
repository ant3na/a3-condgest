import streamlit as st
import os
from datetime import datetime

from db import get_session
from models import Assembleia, Sondagem, VotoSondagem, Condomino, Documento
from utils import configurar_sidebar, enviar_email_real, gerar_pdf_ata, REPORTLAB_INSTALLED, hoje

session = get_session()

mes_sel, ano_sel, str_inicio, str_fim, mes_str = configurar_sidebar()

st.header(":material/diversity_3: Assembleias e Votações")
tab_reunioes, tab_votos = st.tabs(["📅 Reuniões de Condomínio", "📊 Votações & Sondagens"])

with tab_reunioes:
    if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
        with st.expander(":material/add_alert: Agendar Nova Assembleia"):
            with st.form("f_ass"):
                tit = st.text_input("Título *", key=f"a_t_{st.session_state.get('form_key', 0)}")
                data_reuniao = st.date_input("Data da Reunião", key=f"a_d_{st.session_state.get('form_key', 0)}")
                assuntos = st.text_area("Ordem de Trabalhos (Assuntos) *", key=f"a_a_{st.session_state.get('form_key', 0)}")
                enviar_email_convocatoria = st.checkbox("Enviar convocatória por email a todos", value=True, key=f"a_e_{st.session_state.get('form_key', 0)}")
                
                if st.form_submit_button("Agendar"):
                    if not tit.strip() or not assuntos.strip(): st.error("⚠️ Título e Ordem de Trabalhos obrigatórios.")
                    else:
                        session.add(Assembleia(titulo=tit, data_agendada=data_reuniao.strftime("%Y-%m-%d"), assuntos=assuntos))
                        session.commit()
                        if enviar_email_convocatoria:
                            condominos_com_email = session.query(Condomino).filter(Condomino.email.isnot(None), Condomino.email != "").all()
                            emails_enviados = 0
                            for c in condominos_com_email:
                                corpo = f"Exmo(a) Sr(a) {c.nome},\n\nConvocatória para a reunião de condomínio: {tit}.\nData: {data_reuniao.strftime('%d/%m/%Y')}\n\nAssuntos:\n{assuntos}\n\nAdministração."
                                if enviar_email_real(c.email, f"Convocatória - {tit}", corpo): emails_enviados += 1
                            st.session_state.toast = (f"Assembleia agendada! {emails_enviados} convites enviados.", "✅")
                        else: st.session_state.toast = ("Assembleia agendada!", "✅")
                        st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()

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
                        if col_act.button("Mark Realizada", key=f"real_{r.id}", use_container_width=True): r.realizada = True; session.commit(); st.rerun()
                    else:
                        if col_act.button("Reabrir", key=f"undo_{r.id}", use_container_width=True): r.realizada = False; session.commit(); st.rerun()
                    if col_act.button("🗑️ Eliminar", key=f"del_ass_{r.id}", use_container_width=True): session.delete(r); session.commit(); st.rerun()
                        
                if r.realizada:
                    if st.session_state.perfil == "Admin" and not st.session_state.modo_leitura:
                        with st.expander("📝 Redigir / Exportar Ata Digital", expanded=False):
                            texto_atual = r.texto_ata if r.texto_ata else "Decisões tomadas na reunião de condomínio..."
                            novo_texto = st.text_area("Corpo da Ata", value=texto_atual, height=150, key=f"ata_txt_{r.id}")
                            if st.button("💾 Gravar Ata", key=f"save_{r.id}", type="primary"):
                                r.texto_ata = novo_texto; session.commit(); st.toast("Gravado!", icon="✅")
                            
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
                                        session.commit(); st.success("Arquivada!")
                                if c_m.button("📧 Enviar por Email", key=f"mail_{r.id}"):
                                    conds_email = session.query(Condomino).filter(Condomino.email.isnot(None), Condomino.email != "").all()
                                    enviados = 0
                                    for c in conds_email:
                                        if enviar_email_real(c.email, f"Ata de Assembleia - {r.titulo}", "Segue em anexo a ata.", anexo_bytes=pdf_ata, nome_anexo=nome_ficheiro): enviados += 1
                                    st.success(f"Enviada para {enviados} proprietários!")
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
                        session.commit(); st.session_state.form_key = st.session_state.get('form_key', 0) + 1; st.rerun()

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
                                session.commit(); st.rerun()

                if st.session_state.perfil == "Admin":
                    c_act1, c_act2 = st.columns(2)
                    if c_act1.button("Abrir/Fechar", key=f"alt_{s.id}"): s.ativa = not s.ativa; session.commit(); st.rerun()
                    if c_act2.button("Apagar Votação", key=f"del_s_{s.id}"):
                        session.query(VotoSondagem).filter_by(sondagem_id=s.id).delete()
                        session.delete(s); session.commit(); st.rerun()
    else: 
        st.info("Não existem votações de momento.")