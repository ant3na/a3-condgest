from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import date

Base = declarative_base()

class Condomino(Base):
    __tablename__ = 'condominos'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    fracao = Column(String, nullable=False, unique=True)
    nif = Column(String) 
    telefone = Column(String)
    email = Column(String)
    permilagem = Column(Float, default=0.0) 
    quotas = relationship("Quota", back_populates="condomino", cascade="all, delete-orphan")
    utilizadores = relationship("Utilizador", back_populates="condomino", cascade="all, delete-orphan")

class Utilizador(Base):
    __tablename__ = 'utilizadores'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    perfil = Column(String, nullable=False, default='Morador') # 'Admin' ou 'Morador'
    condomino_id = Column(Integer, ForeignKey('condominos.id'), nullable=True) 
    condomino = relationship("Condomino", back_populates="utilizadores")
    perm_dashboard = Column(Boolean, default=False)
    perm_condominos = Column(Boolean, default=False)
    perm_quotas = Column(Boolean, default=False)
    perm_financas = Column(Boolean, default=False)
    perm_recibos = Column(Boolean, default=False)
    perm_assembleias = Column(Boolean, default=False)
    perm_arquivo = Column(Boolean, default=False)
    perm_fornecedores = Column(Boolean, default=False)
    perm_ocorrencias = Column(Boolean, default=False)
    modo_leitura = Column(Boolean, default=False) 
    perm_download_docs = Column(Boolean, default=True)
    perm_mural = Column(Boolean, default=True)

class Quota(Base):
    __tablename__ = 'quotas'
    id = Column(Integer, primary_key=True)
    condomino_id = Column(Integer, ForeignKey('condominos.id'))
    mes_ano = Column(String, nullable=False) 
    valor = Column(Float, nullable=False)
    paga = Column(Boolean, default=False)
    data_pagamento = Column(String, nullable=True) 
    condomino = relationship("Condomino", back_populates="quotas")

class Movimento(Base):
    __tablename__ = 'movimentos'
    id = Column(Integer, primary_key=True)
    tipo = Column(String, nullable=False)
    descricao = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    data = Column(String, nullable=False)

class Ocorrencia(Base):
    __tablename__ = 'ocorrencias'
    id = Column(Integer, primary_key=True)
    titulo = Column(String, nullable=False)
    descricao = Column(String)
    resolvida = Column(Boolean, default=False)
    data_criacao = Column(String, default=date.today().strftime("%Y-%m-%d"))
    criado_por = Column(String, nullable=True)
    foto1 = Column(String, nullable=True)
    foto2 = Column(String, nullable=True)

class Orcamento(Base):
    __tablename__ = 'orcamentos'
    id = Column(Integer, primary_key=True)
    ano = Column(Integer, nullable=False, unique=True)
    valor_anual = Column(Float, nullable=False)

class Documento(Base):
    __tablename__ = 'documentos'
    id = Column(Integer, primary_key=True)
    nome_ficheiro = Column(String, nullable=False)
    categoria = Column(String, nullable=False) 
    caminho = Column(String, nullable=False)
    data_upload = Column(String, default=date.today().strftime("%Y-%m-%d"))
    carregado_por = Column(String, nullable=True)

class Fornecedor(Base):
    __tablename__ = 'fornecedores'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    telefone = Column(String)
    email = Column(String)
    nif = Column(String)
    observacoes = Column(String)
    responsavel = Column(String)
    iban = Column(String)

class Assembleia(Base):
    __tablename__ = 'assembleias'
    id = Column(Integer, primary_key=True)
    data_agendada = Column(String, nullable=False)
    titulo = Column(String, nullable=False)
    assuntos = Column(String, nullable=False)
    realizada = Column(Boolean, default=False)
    texto_ata = Column(String, nullable=True) 
    ata_aprovada = Column(Boolean, default=False)

class Sondagem(Base):
    __tablename__ = 'sondagens'
    id = Column(Integer, primary_key=True)
    pergunta = Column(String, nullable=False)
    opcoes = Column(String, default="Favor, Contra, Abstenção")
    ativa = Column(Boolean, default=True)
    data_criacao = Column(String, default=date.today().strftime("%Y-%m-%d"))

class VotoSondagem(Base):
    __tablename__ = 'votos_sondagem'
    id = Column(Integer, primary_key=True)
    sondagem_id = Column(Integer, ForeignKey('sondagens.id'), nullable=False)
    condomino_id = Column(Integer, ForeignKey('condominos.id'), nullable=False)
    resposta = Column(String, nullable=False)

class Anuncio(Base):
    __tablename__ = 'anuncios'
    id = Column(Integer, primary_key=True)
    titulo = Column(String, nullable=False)
    mensagem = Column(String, nullable=False)
    data_criacao = Column(String, default=date.today().strftime("%Y-%m-%d %H:%M"))
    criado_por = Column(String, nullable=False)
    fracao = Column(String, nullable=True)

class LogAuditoria(Base):
    __tablename__ = 'logs_auditoria'
    id = Column(Integer, primary_key=True)
    data_hora = Column(String, nullable=False)
    utilizador = Column(String, nullable=False)
    acao = Column(String, nullable=False)
    detalhe = Column(String, nullable=True)

class Equipamento(Base):
    __tablename__ = 'equipamentos'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    localizacao = Column(String, nullable=True)
    data_ultima_inspecao = Column(String, nullable=True)
    data_proxima_inspecao = Column(String, nullable=True)
    notas = Column(String, nullable=True)
