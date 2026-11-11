import os 
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
    DB_NOME = os.environ.get("DB_NOME", "biblioteca_saber")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NOME}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "chave-para-desenvolvimento-trocar-em-producao"
    )

    SESSION_COOKIE_NAME = "session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    MAX_IMAGE_SIZE = 5 * 1024 * 1024
    MIN_IMAGE_WIDTH = 100
    MIN_IMAGE_HEIGHT = 140
    MAX_IMAGE_WIDTH = 3000
    MAX_IMAGE_HEIGHT = 4000
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}