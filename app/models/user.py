from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..utils.datas import agora

PERFIS = {"admin": "Administrador", "operador": "Operador"}


class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default="operador")
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    def set_senha(self, senha: str) -> None:
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha: str) -> bool:
        return check_password_hash(self.senha_hash, senha or "")

    @property
    def is_active(self) -> bool:  # usado pelo Flask-Login
        return bool(self.ativo)

    @property
    def is_admin(self) -> bool:
        return self.perfil == "admin"

    @property
    def perfil_nome(self) -> str:
        return PERFIS.get(self.perfil, self.perfil)

    @property
    def primeiro_nome(self) -> str:
        return (self.nome or "").split(" ")[0]
