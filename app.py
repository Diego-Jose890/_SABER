import os
import re
import uuid
from datetime import datetime

from flask import Flask, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError

import models
import seed
from extensions import db, login_manager
from decorators import admin_required
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

models.criar_banco_se_nao_existir()

db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()
    seed.popular_dados_exemplo()

@login_manager.user_loader
def carregar_usuario(identificador):
    return models.carregar_conta(identificador)

def destino_seguro(destino):
    return (
        bool(destino)
        and destino.startswith("/")
        and not destino.startswith("//")
        and "\\" not in destino
    )

def salvar_imagem(arquivo):
    if arquivo is None or not arquivo.filename:
        return None, "Selecione uma imagem."

    extensao = arquivo.filename.rsplit(".", 1)[-1].lower()
    formatos = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
    if extensao not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        return None, "Envie uma imagem JPG, PNG ou WEBP."

    arquivo.stream.seek(0, 2)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)
    if tamanho == 0:
        return None, "O arquivo está vazio."
    if tamanho > current_app.config["MAX_IMAGE_SIZE"]:
        return None, "A imagem deve ter no máximo 5 MB."

    try:
        imagem = Image.open(arquivo.stream)
        if imagem.format != formatos[extensao]:
            return None, "A extensão não corresponde ao formato real da imagem."

        largura, altura = imagem.size
        if largura < current_app.config["MIN_IMAGE_WIDTH"] or altura < current_app.config["MIN_IMAGE_HEIGHT"]:
            return None, "A imagem deve ter pelo menos 100 x 140 pixels."
        if largura > current_app.config["MAX_IMAGE_WIDTH"] or altura > current_app.config["MAX_IMAGE_HEIGHT"]:
            return None, "A imagem não pode ultrapassar 3000 x 4000 pixels."

        imagem.verify()
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError
    ):
        return None, "O arquivo enviado não é uma imagem válida."

    nome_arquivo = f"{uuid.uuid4().hex}.{extensao}"
    pasta = os.path.join(current_app.static_folder, "uploads", "livros")
    os.makedirs(pasta, exist_ok=True)
    arquivo.stream.seek(0)
    arquivo.save(os.path.join(pasta, nome_arquivo))

    return f"uploads/livros/{nome_arquivo}", None

def remover_arquivo_imagem(caminho_relativo):
    if not caminho_relativo or not caminho_relativo.startswith("uploads/livros/"):
        return

    nome_arquivo = os.path.basename(caminho_relativo)
    caminho = os.path.join(current_app.static_folder, "uploads", "livros", nome_arquivo)
    if os.path.isfile(caminho):
        os.remove(caminho)

def isbn_valido(isbn):
    if not (isbn.isascii() and isbn.isdigit() and len(isbn) == 13):
        return False
    soma = sum(int(digito) * (1 if indice % 2 == 0 else 3) for indice, digito in enumerate(isbn[:12]))
    return (10 - soma % 10) % 10 == int(isbn[-1])

def cpf_valido(cpf):
    if not (cpf.isascii() and cpf.isdigit() and len(cpf) == 11):
        return False
    if cpf == cpf[0] * 11:
        return False
    soma1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito1 = (soma1 * 10) % 11
    digito1 = 0 if digito1 == 10 else digito1
    soma2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito2 = (soma2 * 10) % 11
    digito2 = 0 if digito2 == 10 else digito2
    return cpf[-2:] == f"{digito1}{digito2}"

def validar_livro(form, livro_id=None, exigir_imagem=True):
    titulo = form.get("titulo", "").strip()
    autor = form.get("autor", "").strip()
    isbn = form.get("isbn", "").strip().replace("-", "").replace(" ", "")
    
    generos_por_id = {str(g.id): g for g in models.listar_generos()}
    genero = generos_por_id.get(form.get("id_genero", ""))
    
    erros = []
    
    if not titulo:
        erros.append("Informe o título.")
    elif len(titulo) > 100:
        erros.append("O título deve ter no máximo 100 caracteres.")
    
    if not autor:
        erros.append("Informe o autor.")
    elif len(autor) > 100:
        erros.append("O autor deve ter no máximo 100 caracteres.")
    
    if not isbn_valido(isbn):
        erros.append("Informe um ISBN-13 válido, com 13 números e dígito verificador correto.")
    else:
        existente = models.buscar_livro_por_isbn(isbn)
        if existente is not None and existente.id != livro_id:
            erros.append("Já existe um livro cadastrado com esse ISBN.")

    if exigir_imagem and not request.files.get("imagem", None):
        erros.append("Selecione a imagem da capa.")

    if genero is None:
        erros.append("Selecione um gênero válido.")

    dados = {
        "titulo": titulo,
        "autor": autor,
        "isbn": isbn,
        "genero": genero,
    }
    return erros, dados

def validar_usuario(form, usuario_id=None):
    nome = form.get("nome", "").strip()
    telefone = re.sub(r"\D", "", form.get("telefone", ""))
    cpf = re.sub(r"\D", "", form.get("cpf", ""))
    
    erros = []
    
    if not nome:
        erros.append("Informe o nome do usuário.")
    elif len(nome) > 25:
        erros.append("O nome deve ter no máximo 25 caracteres.")

    if not (telefone.isascii() and len(telefone) in (10, 11)):
        erros.append("Informe um telefone com DDD (10 ou 11 números).")

    if not cpf_valido(cpf):
        erros.append("Informe um CPF válido, com 11 números e dígitos verificadores corretos.")
    else:
        existente = models.buscar_usuario_por_cpf(cpf)
        if existente is not None and existente.id != usuario_id:
            erros.append("Já existe um usuário cadastrado com esse CPF.")

    dados = {
        "nome": nome,
        "telefone": telefone,
        "cpf": cpf,
    }
    
    return erros, dados

def converter_data(valor):
    if not valor:
        return None
    for formato in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            continue
    return None

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("admin_painel"))
    return redirect(url_for("catalogo"))

@app.route("/catalogo")
def catalogo():
    busca = request.args.get("busca", "").strip()
    genero_id = request.args.get("genero", type=int)
    ordem = request.args.get("ordem", "recentes")
    disponibilidade = request.args.get("disponibilidade", "")
    livros = models.listar_livros(busca, genero_id, ordem, disponibilidade, status=True)
    return render_template(
        "catalogo.html", 
        livros=livros, 
        generos=models.listar_generos(),
        busca=busca, 
        genero_selecionado=genero_id,
        ordem=ordem, 
        disponibilidade=disponibilidade,
    )

@app.route("/livros/<int:livro_id>")
def detalhes_livro(livro_id):
    livro = models.buscar_livro(livro_id)
    if livro is None or not livro.status:
        abort(404)
    return render_template("livro_detalhe.html", livro=livro)

@app.route("/portal_interno_login", methods=["GET", "POST"])
def entrar():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
 
    proxima = request.form.get("next") or request.args.get("next") or ""
 
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
 
        if not email or not senha:
            flash("Informe e-mail e senha.", "erro")
            return render_template("entrar.html", email=email, proxima=proxima)
 
        conta = models.buscar_conta_por_email(email)
 
        if conta is None or not conta.verificar_senha(senha):
            flash("E-mail ou senha inválidos.", "erro")
            return render_template("entrar.html", email=email, proxima=proxima)
 
        login_user(conta)
        if destino_seguro(proxima):
            return redirect(proxima)
        return redirect(url_for("index"))
 
    return render_template("entrar.html", email="", proxima=proxima)

@app.route("/sair")
@login_required
def sair():
    logout_user()
    flash("Sessão encerrada.", "sucesso")
    return redirect(url_for("catalogo"))

@app.route("/admin")
@admin_required
def admin_painel():
    total_usuarios = models.Usuario.query.count()
    total_livros = models.Livro.query.filter_by(status=True).count()
    total_emprestimos = models.Emprestimo.query.filter_by(
        status=models.STATUS_ATIVO
    ).count()
    total_atrasados = sum(1 for e in models.listar_emprestimos(status=models.STATUS_ATIVO) if e.atrasado)
    return render_template(
        "admin_painel.html",
        total_usuarios=total_usuarios,
        total_livros=total_livros,
        total_emprestimos=total_emprestimos,
        total_atrasados=total_atrasados,
    )

@app.route("/admin/livros")
@admin_required
def admin_livros():
    busca = request.args.get("busca", "").strip()
    genero_id = request.args.get("genero", type=int)
    ordem = request.args.get("ordem", "recentes")
    disponibilidade = request.args.get("disponibilidade", "")
    livros = models.listar_livros(busca, genero_id, ordem, disponibilidade, status=True)
    return render_template(
        "admin_livros.html", 
        livros=livros, 
        generos=models.listar_generos(),
        busca=busca,
        genero_selecionado=genero_id,
        ordem=ordem,
        disponibilidade=disponibilidade
    )

@app.route("/admin/livros/removidos")
@admin_required
def admin_livros_removidos():
    livros = models.Livro.query.filter_by(status=False).order_by(models.Livro.titulo.asc()).all()
    return render_template(
        "admin_livros_removidos.html",
        livros=livros
    )

@app.route("/admin/livros/novo", methods=["GET", "POST"])
@admin_required
def admin_livro_novo():
    if request.method == "POST":
        erros, dados = validar_livro(request.form)

        caminho_novo = None

        if not erros:
            caminho_novo, erro_imagem = salvar_imagem(request.files.get("imagem"))
            if erro_imagem:
                erros.append(erro_imagem)
        if erros:
            return render_template("admin_livro_novo.html", generos=models.listar_generos(), valores=request.form, erros=erros)
        try:
            models.criar_livro(
                dados["titulo"],
                dados["autor"],
                dados["isbn"],
                caminho_novo,
                dados["genero"].id,
                current_user.id
            )
        except IntegrityError:
            db.session.rollback()
            remover_arquivo_imagem(caminho_novo)
            flash("Não foi possível cadastrar o livro. Verifique se o ISBN já está cadastrado.", "erro")
            return redirect(url_for("admin_livro_novo"))

        flash("Livro cadastrado com sucesso.", "sucesso")
        return redirect(url_for("admin_livros"))
    
    return render_template(
        "admin_livro_novo.html",
        generos=models.listar_generos(),
        valores={},
        erros=[]
    )

@app.route("/admin/livros/<int:livro_id>/editar", methods=["GET", "POST"])
@admin_required
def admin_livro_editar(livro_id):
    livro = models.buscar_livro(livro_id)
    if livro is None:
        abort(404)
    if request.method == "POST":
        arquivo = request.files.get("imagem")
        erros, dados = validar_livro(request.form, livro_id, exigir_imagem=False)
        caminho_novo = livro.imagem
        if arquivo and arquivo.filename and not erros:
            caminho_novo, erro_imagem = salvar_imagem(arquivo)
            if erro_imagem:
                erros.append(erro_imagem)
        if erros:
            return render_template("admin_livro_editar.html", livro=livro, generos=models.listar_generos(), valores=request.form, erros=erros)
        caminho_antigo = livro.imagem
        try:
            models.atualizar_livro(
                livro_id, 
                dados["titulo"], 
                dados["autor"], 
                dados["isbn"], 
                caminho_novo, dados["genero"].id
            )
        except IntegrityError:
            db.session.rollback()
            if caminho_novo != caminho_antigo:
                remover_arquivo_imagem(caminho_novo)
            flash("Não foi possível atualizar o livro. Verifique o ISBN.", "erro")
            return redirect(url_for("admin_livro_editar", livro_id=livro_id))
        if caminho_novo != caminho_antigo:
            remover_arquivo_imagem(caminho_antigo)
        flash("Livro atualizado com sucesso.", "sucesso")
        return redirect(url_for("admin_livros"))
    return render_template(
        "admin_livro_editar.html", 
        livro=livro, 
        generos=models.listar_generos(), 
        valores={}, 
        erros=[]
    )

@app.route("/admin/livros/<int:livro_id>/remover", methods=["POST"])
@admin_required
def admin_livro_remover(livro_id):
    livro = models.buscar_livro(livro_id)
    if livro is None:
        abort(404)
    if not livro.status:
        flash("Este livro já está na lista de removidos.", "erro")
        return redirect(url_for("admin_livros"))
    if models.emprestimo_ativo_do_livro(livro_id) or not livro.disponibilidade:
        flash("Não é possível remover um livro que possui empréstimo ativo.", "erro")
        return redirect(url_for("admin_livros"))
    livro.status = False
    db.session.commit()
    flash("Livro removido do acervo. Ele pode ser restaurado posteriormente.", "sucesso")
    return redirect(url_for("admin_livros"))

@app.route("/admin/livros/<int:livro_id>/restaurar", methods=["POST"])
@admin_required
def admin_livro_restaurar(livro_id):
    livro = models.buscar_livro(livro_id)
    if livro is None:
        abort(404)

    if livro.status:
        flash("Este livro já está no acervo.", "erro")
        return redirect(url_for("admin_livros_removidos"))

    if models.emprestimo_ativo_do_livro(livro_id):
        flash("Não é possível restaurar o livro enquanto houver empréstimo ativo.", "erro")
        return redirect(url_for("admin_livros_removidos"))

    livro.status = True
    livro.disponibilidade = True
    db.session.commit()
    flash("Livro restaurado ao acervo com sucesso.", "sucesso")
    return redirect(url_for("admin_livros_removidos"))

@app.route("/admin/cadastro_user", methods=["GET", "POST"])
@admin_required
def admin_cadastro_usuario():
    if request.method == "POST":
        erros, dados = validar_usuario(request.form)
        if erros:
            return render_template("admin_cadastro_usuario.html", valores=request.form, erros=erros)
        try:
            models.criar_usuario(dados["nome"], dados["telefone"], dados["cpf"])
        except IntegrityError:
            db.session.rollback()
            flash("Não foi possível cadastrar. Verifique se o CPF já existe.", "erro")
            return redirect(url_for("admin_cadastro_usuario"))
        flash("Usuário cadastrado com sucesso.", "sucesso")
        return redirect(url_for("admin_usuarios"))
    return render_template("admin_cadastro_usuario.html", valores={}, erros=[])

@app.route("/admin/usuarios")
@admin_required
def admin_usuarios():
    busca = request.args.get("busca", "").strip()
    usuarios = models.listar_usuarios(busca)
    return render_template("admin_usuarios.html", usuarios=usuarios, busca=busca)

@app.route("/admin/emprestimos")
@admin_required
def admin_emprestimos():
    status = request.args.get("status", "")
    busca = request.args.get("busca", "").strip()
    emprestimos = models.listar_emprestimos(status=status, busca=busca)
    return render_template("admin_emprestimos.html", emprestimos=emprestimos, status_selecionado=status, busca=busca)

@app.route("/admin/emprestimos/<int:emprestimo_id>", methods=["GET", "POST"])
@admin_required
def admin_emprestimo_detalhe(emprestimo_id):
    emprestimo = models.buscar_emprestimo(emprestimo_id)
    if emprestimo is None:
        abort(404)
    if request.method == "POST":
        try:
            models.registrar_devolucao(emprestimo_id)
        except ValueError as erro:
            flash(str(erro), "erro")
        else:
            flash("Devolução registrada. O livro voltou a ficar disponível.", "sucesso")
        return redirect(url_for("admin_emprestimo_detalhe", emprestimo_id=emprestimo_id))
    return render_template("admin_emprestimo_detalhe.html", emprestimo=emprestimo)

@app.route("/admin/emprestimos/cadastro_emprestimo", methods=["GET", "POST"])
@admin_required
def admin_emprestimo_novo():
    usuarios = models.listar_usuarios()
    livros = models.Livro.query.filter_by(status=True, disponibilidade=True).order_by(models.Livro.titulo.asc()).all()
    if request.method == "POST":
        usuario_id = request.form.get("id_usuario", type=int)
        livro_id = request.form.get("id_livro", type=int)
        retirada = converter_data(request.form.get("data_retirada", ""))
        prevista = converter_data(request.form.get("data_devolucao_prevista", ""))

        erros = []

        if models.buscar_usuario(usuario_id) is None:
            erros.append("Selecione um usuário válido.")
        if models.buscar_livro(livro_id) is None:
            erros.append("Selecione um livro válido.")
        if retirada is None:
            erros.append("Informe uma data de retirada válida.")
        if prevista is None:
            erros.append("Informe uma data de devolução prevista válida.")
        if retirada and prevista and prevista <= retirada:
            erros.append("A devolução prevista deve ser posterior à retirada.")
        if usuario_id and models.emprestimo_ativo_do_usuario(usuario_id):
            erros.append("Este usuário já possui um empréstimo ativo.")
        livro = models.buscar_livro(livro_id) if livro_id else None
        if livro and (not livro.status or not livro.disponibilidade or models.emprestimo_ativo_do_livro(livro_id)):
            erros.append("O livro selecionado não está disponível.")
        if erros:
            return render_template("admin_emprestimo_novo.html", usuarios=usuarios, livros=livros, valores=request.form, erros=erros)
        try:
            models.criar_emprestimo(usuario_id, livro_id, retirada, prevista)
        except (ValueError, IntegrityError) as erro:
            db.session.rollback()
            mensagem = str(erro) if isinstance(erro, ValueError) else "Não foi possível registrar: o usuário ou livro já possui empréstimo ativo."
            flash(mensagem, "erro")
            return redirect(url_for("admin_emprestimo_novo"))
        flash("Empréstimo cadastrado com sucesso.", "sucesso")
        return redirect(url_for("admin_emprestimos"))
    return render_template(
        "admin_emprestimo_novo.html", 
        usuarios=usuarios, 
        livros=livros, 
        valores={}, 
        erros=[]
    )

@app.errorhandler(413)
def arquivo_muito_grande(_erro):
    flash("A imagem excede o limite permitido de 5 MB.", "erro")
    return redirect(request.referrer or url_for("admin_livro_novo"))

if __name__ == "__main__":
    app.run(debug=True)