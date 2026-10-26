"""Usuários e autenticação."""
import re

from sqlalchemy import func

from ..extensions import db
from ..models import User
from ..models.user import PERFIS
from .errors import RegraNegocioError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SENHA_MINIMA = 6


def autenticar(email: str, senha: str) -> User | None:
    usuario = User.query.filter(func.lower(User.email) == (email or "").strip().lower()).first()
    if usuario and usuario.ativo and usuario.check_senha(senha):
        return usuario
    return None


def salvar_usuario(dados: dict, usuario: User | None = None, editor: User | None = None) -> User:
    erros = {}
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    perfil = dados.get("perfil") or "operador"
    senha = dados.get("senha") or ""
    ativo = str(dados.get("ativo", "on")).lower() in ("on", "1", "true")

    if not nome:
        erros["nome"] = "Informe o nome."
    if not EMAIL_RE.match(email):
        erros["email"] = "Informe um e-mail válido (ex.: maria@email.com)."
    elif User.query.filter(func.lower(User.email) == email, User.id != (usuario.id if usuario else None)).first():
        erros["email"] = "Já existe um usuário com este e-mail."
    if perfil not in PERFIS:
        erros["perfil"] = "Perfil inválido."
    if usuario is None or senha:
        if len(senha) < SENHA_MINIMA:
            erros["senha"] = f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."
        elif senha != (dados.get("senha_confirmacao") or ""):
            erros["senha_confirmacao"] = "A confirmação não confere com a senha."

    if usuario is not None and (perfil != "admin" or not ativo) and usuario.is_admin and usuario.ativo:
        outros_admins = User.query.filter(User.perfil == "admin", User.ativo.is_(True), User.id != usuario.id).count()
        if outros_admins == 0:
            erros["perfil"] = "É preciso manter pelo menos um administrador ativo."
    if usuario is not None and editor is not None and usuario.id == editor.id and not ativo:
        erros["ativo"] = "Você não pode desativar o seu próprio usuário."

    if erros:
        raise RegraNegocioError("Corrija os campos destacados e tente novamente.", erros)

    if usuario is None:
        usuario = User()
        db.session.add(usuario)
    usuario.nome = nome
    usuario.email = email
    usuario.perfil = perfil
    usuario.ativo = ativo
    if senha:
        usuario.set_senha(senha)
    db.session.commit()
    return usuario


def criar_usuario_inicial(nome, email, senha, perfil="admin") -> User:
    usuario = User.query.filter_by(email=email).first()
    if usuario is None:
        usuario = User(nome=nome, email=email, perfil=perfil, ativo=True)
        usuario.set_senha(senha)
        db.session.add(usuario)
        db.session.commit()
    return usuario
