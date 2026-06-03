import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

# 1. Tentar ler o link da base de dados na Cloud (Supabase). 
# Se falhar (ou não existir o ficheiro secrets), cai para a base de dados local SQLite.
try:
    db_url = st.secrets.get("DATABASE_URL", "sqlite:///condominio.db")
except Exception:
    db_url = "sqlite:///condominio.db"

# 2. Correção de sintaxe: O SQLAlchemy moderno exige que o link comece por 'postgresql://'
# Mas muitos serviços na nuvem (como Supabase ou Render) fornecem 'postgres://'
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# 3. Criação do Engine (Motor da Base de Dados)
# O argumento "check_same_thread" só é necessário/suportado no SQLite
if db_url.startswith("sqlite"):
    engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})
else:
    engine = create_engine(db_url, echo=False)

# 4. Criar a fábrica de sessões
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    # Cria a pasta para guardar os documentos físicos, se não existir
    os.makedirs("uploads", exist_ok=True)
    # Cria as tabelas na base de dados (se ainda não existirem)
    Base.metadata.create_all(bind=engine)

def get_session():
    # Devolve uma nova sessão sempre que a aplicação precisar de falar com a base de dados
    return SessionLocal()