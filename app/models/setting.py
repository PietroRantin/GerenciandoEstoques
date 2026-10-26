from ..extensions import db


class Setting(db.Model):
    """Parâmetros de negócio alterados pelo administrador (ver config.DEFAULT_SETTINGS)."""

    __tablename__ = "configuracoes"

    chave = db.Column(db.String(50), primary_key=True)
    valor = db.Column(db.String(255), nullable=False)
