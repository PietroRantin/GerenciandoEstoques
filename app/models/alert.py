from ..extensions import db
from ..utils.datas import agora

TIPOS_ALERTA = {
    "sem_estoque": "Sem estoque",
    "estoque_baixo": "Precisa de reposição",
    "vencido": "Vencido",
    "vencendo": "Vencendo",
}
NIVEIS = {
    "critico": ("Urgente", "danger", 3),
    "alto": ("Atenção", "warning", 2),
    "medio": ("Aviso", "info", 1),
}


class Alert(db.Model):
    """Alertas gerados automaticamente pelo alert_service.

    Um alerta fica aberto enquanto a condição existir e é marcado como
    resolvido automaticamente quando ela deixa de existir (ex.: após uma
    entrada de estoque), mantendo o histórico.
    """

    __tablename__ = "alertas"
    __table_args__ = (db.Index("ix_alerta_aberto", "resolvido", "tipo"),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False, index=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lotes.id"))
    tipo = db.Column(db.String(20), nullable=False)
    mensagem = db.Column(db.String(255), nullable=False)
    nivel = db.Column(db.String(10), nullable=False, default="medio")
    resolvido = db.Column(db.Boolean, nullable=False, default=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)
    resolvido_em = db.Column(db.DateTime)

    produto = db.relationship("Product")
    lote = db.relationship("Lote")

    @property
    def nivel_info(self):
        return NIVEIS.get(self.nivel, ("Aviso", "info", 1))

    @property
    def tipo_nome(self):
        return TIPOS_ALERTA.get(self.tipo, self.tipo)
