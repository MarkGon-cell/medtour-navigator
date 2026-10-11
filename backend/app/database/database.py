from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()
env_backend = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_backend):
    load_dotenv(env_backend)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:694200@localhost:5432/medtour_db")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()