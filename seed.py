from datetime import datetime

from extensions import db
from models import Administrador, Emprestimo, Genero, Livro, Usuario, STATUS_ATIVO, STATUS_DEVOLVIDO

# Nota: as contas abaixo são de TESTE para o desenvolvimento
ADMINISTRADORES = [
    {"nome": "Admin123", "email": "teste.admin@gmail.com", "senha": "admin123"},
]

USUARIOS = [
    {"nome": "Diego_Samuel", "telefone": "11987654321", "cpf": "12345678901"},
    {"nome": "Thalys_Rafael", "telefone": "21976543210", "cpf": "98765432100"},
    {"nome": "Paulo_Henrique", "telefone": "21987654321", "cpf": "98765432101"},
    {"nome": "Victor_Manoel", "telefone": "31965432109", "cpf": "45678912300"},
]

GENEROS = [
    "Ação", "Aventura", "Biografia", "Clássico", "Comédia", "Drama", "Fantasia", "Ficção Científica", "História", "Horror", "Infantil",
    "Juvenil", "Mistério", "Poesia", "Romance", "Suspense", "Terror", "Thriller", "Novela", "Autobiografia",
]

LIVROS = []

EMPRESTIMOS = []

def popular_dados_exemplo():
    if Administrador.query.count() == 0:
        for item in ADMINISTRADORES:
            admin = Administrador(nome=item["nome"], email=item["email"])
            admin.definir_senha(item["senha"])
            db.session.add(admin)
        db.session.commit()

    if Genero.query.count() == 0:
        for nome in GENEROS:
            db.session.add(Genero(nome=nome))
        db.session.commit()

    if Usuario.query.count() == 0:
        for item in USUARIOS:
            db.session.add(Usuario(
                nome=item["nome"],
                telefone=item["telefone"],
                cpf=item["cpf"],
            ))
        db.session.commit()

if __name__ == "__main__":
    from app import app

    with app.app_context():
        popular_dados_exemplo()
        print("Banco populado com administrador, usuários e gêneros. Os empréstimos e livros devem ser cadastrados só com as imagens.")