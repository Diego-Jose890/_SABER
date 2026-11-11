from datetime import datetime

import psycopg2
from psycopg2 import sql
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from extensions import db

STATUS_ATIVO = "ativo"
STATUS_DEVOLVIDO = "devolvido"

TIPO_ADMIN = "admin"
TIPO_USUARIO = "usuario"

def criar_banco_se_nao_existir():
    conexao = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        dbname="postgres",
    )
    conexao.autocommit = True
    cursor = conexao.cursor()
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (Config.DB_NOME,))
    if cursor.fetchone() is None:
        cursor.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(Config.DB_NOME))
        )
    cursor.close()
    conexao.close()

class Usuario(db.Model, UserMixin):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(25), nullable=False)
    telefone = db.Column(db.String(15), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
 
    def __repr__(self):
        return f"<Usuario {self.id} - {self.nome}>"

class Administrador(db.Model, UserMixin):
    __tablename__ = "administrador"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
 
    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
 
    @property
    def is_admin(self):
        return True
 
    def __repr__(self):
        return f"<Administrador {self.id} - {self.email}>"

class Genero(db.Model):
    __tablename__ = "genero"
 
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
 
    def __repr__(self):
        return f"<Genero {self.nome}>"

class Livro(db.Model):
    __tablename__ = "livro"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    autor = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(13), unique=True, nullable=False)
    imagem = db.Column(db.String(254), nullable=False)

    id_genero = db.Column(db.Integer, db.ForeignKey("genero.id"), nullable=False)
    genero = db.relationship("Genero", backref=db.backref("livros", lazy=True))

    id_administrador_cadastro = db.Column(db.Integer, db.ForeignKey("administrador.id", ondelete="SET NULL"))
    administrador = db.relationship("Administrador")

    # Nota: True = está no acervo | False = removido
    status = db.Column(db.Boolean, default=True, nullable=False)
    # Nota: True = livre | False = emprestado
    disponibilidade = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Livro {self.id} - {self.titulo}>"

class Emprestimo(db.Model):
    __tablename__ = "emprestimo"

    id = db.Column(db.Integer, primary_key=True)

    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    usuario = db.relationship("Usuario", backref=db.backref("emprestimos", lazy=True))

    id_livro = db.Column(db.Integer, db.ForeignKey("livro.id"), nullable=False)
    livro = db.relationship("Livro", backref=db.backref("emprestimos", lazy=True))

    data_retirada = db.Column(db.DateTime, nullable=False)
    data_devolucao_prevista = db.Column(db.DateTime, nullable=False)
    data_devolucao_real = db.Column(db.DateTime)

    status = db.Column(db.String(20), default=STATUS_ATIVO, nullable=False)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def atrasado(self):
        return self.status == STATUS_ATIVO and datetime.utcnow() > self.data_devolucao_prevista
    
    def __repr__(self):
        return f"<Emprestimo {self.id} - livro {self.id_livro} / usuário {self.id_usuario}>"

def carregar_conta(identificador):
    try:
        id_conta = int(identificador)
    except (ValueError, AttributeError):
        return None
    return db.session.get(Administrador, id_conta)

def buscar_conta_por_email(email):
    return Administrador.query.filter_by(email=email).first()

def listar_generos():
    return Genero.query.order_by(Genero.nome).all()

def buscar_livro(livro_id):
    return db.session.get(Livro, livro_id)

def buscar_livro_por_isbn(isbn):
    return Livro.query.filter_by(isbn=isbn).first()

def listar_livros(busca="", genero_id=None, ordem="recentes", disponibilidade=None, status=True):
    consulta = Livro.query.filter_by(status=status)
    if busca:
        termo = f"%{busca}%"
        consulta = consulta.filter(db.or_(Livro.titulo.ilike(termo), Livro.autor.ilike(termo)))
    if genero_id:
        consulta = consulta.filter_by(id_genero=genero_id)
    if disponibilidade == "disponiveis":
        consulta = consulta.filter_by(disponibilidade=True)
    elif disponibilidade == "emprestados":
        consulta = consulta.filter_by(disponibilidade=False)

    if ordem == "titulo_az":
        consulta = consulta.order_by(Livro.titulo.asc())
    elif ordem == "titulo_za":
        consulta = consulta.order_by(Livro.titulo.desc())
    elif ordem == "disponiveis":
        consulta = consulta.order_by(Livro.disponibilidade.desc(), Livro.titulo.asc())
    else:
        consulta = consulta.order_by(Livro.id.desc())
    return consulta.all()

def criar_livro(titulo, autor, isbn, imagem, id_genero, id_administrador):
    livro = Livro(
        titulo=titulo,
        autor=autor,
        isbn=isbn,
        imagem=imagem,
        id_genero=id_genero,
        id_administrador_cadastro=id_administrador,
    )
    db.session.add(livro)
    db.session.commit()
    return livro.id

def atualizar_livro(livro_id, titulo, autor, isbn, imagem, id_genero):
    livro = db.session.get(Livro, livro_id)
    livro.titulo = titulo
    livro.autor = autor
    livro.isbn = isbn
    livro.imagem = imagem
    livro.id_genero = id_genero
    db.session.commit()

def buscar_usuario(usuario_id):
    return db.session.get(Usuario, usuario_id)

def buscar_usuario_por_cpf(cpf):
    return Usuario.query.filter_by(cpf=cpf).first()

def listar_usuarios(busca=""):
    consulta = Usuario.query
    if busca:
        termo = f"%{busca}%"
        consulta = consulta.filter(db.or_(Usuario.nome.ilike(termo), Usuario.cpf.ilike(termo), Usuario.telefone.ilike(termo)))
    return consulta.order_by(Usuario.nome.asc()).all()

def criar_usuario(nome, telefone, cpf):
    usuario = Usuario(
        nome=nome, 
        telefone=telefone, 
        cpf=cpf
    )
    db.session.add(usuario)
    db.session.commit()
    return usuario.id

def buscar_emprestimo(emprestimo_id):
    return db.session.get(Emprestimo, emprestimo_id)

def listar_emprestimos(status=None, busca=""):
    consulta = Emprestimo.query.join(Usuario).join(Livro)
    if status in (STATUS_ATIVO, STATUS_DEVOLVIDO):
        consulta = consulta.filter(Emprestimo.status == status)
    if busca:
        termo = f"%{busca}%"
        consulta = consulta.filter(db.or_(Livro.titulo.ilike(termo), Usuario.nome.ilike(termo), Usuario.cpf.ilike(termo)))
    return consulta.order_by(Emprestimo.data_solicitacao.desc()).all()

def emprestimo_ativo_do_usuario(usuario_id):
    return Emprestimo.query.filter_by(id_usuario=usuario_id, status=STATUS_ATIVO).first()

def emprestimo_ativo_do_livro(livro_id):
    return Emprestimo.query.filter_by(id_livro=livro_id, status=STATUS_ATIVO).first()

def criar_emprestimo(usuario_id, livro_id, data_retirada, data_devolucao_prevista):
    usuario = buscar_usuario(usuario_id)
    livro = buscar_livro(livro_id)
    if usuario is None or livro is None:
        raise ValueError("Usuário ou livro não encontrado.")
    if not livro.status:
        raise ValueError("Este livro está removido do acervo.")
    if not livro.disponibilidade or emprestimo_ativo_do_livro(livro_id):
        raise ValueError("Este livro não está disponível para empréstimo.")
    if emprestimo_ativo_do_usuario(usuario_id):
        raise ValueError("Este usuário já possui um empréstimo ativo.")
    if data_devolucao_prevista <= data_retirada:
        raise ValueError("A devolução prevista deve ser posterior à retirada.")

    emprestimo = Emprestimo(
        id_usuario=usuario_id,
        id_livro=livro_id,
        data_retirada=data_retirada,
        data_devolucao_prevista=data_devolucao_prevista,
        status=STATUS_ATIVO,
    )
    livro.disponibilidade = False
    db.session.add(emprestimo)
    db.session.commit()
    return emprestimo.id

def registrar_devolucao(emprestimo_id, data_devolucao=None):
    emprestimo = buscar_emprestimo(emprestimo_id)
    if emprestimo is None:
        raise ValueError("Empréstimo não encontrado.")
    if emprestimo.status != STATUS_ATIVO:
        raise ValueError("Este empréstimo já foi encerrado.")
    data_devolucao = data_devolucao or datetime.utcnow()
    if data_devolucao < emprestimo.data_retirada:
        raise ValueError("A devolução não pode ser anterior à retirada.")

    emprestimo.status = STATUS_DEVOLVIDO
    emprestimo.data_devolucao_real = data_devolucao
    emprestimo.livro.disponibilidade = True
    db.session.commit()
    return True

#Continuem com outras funções abaixo