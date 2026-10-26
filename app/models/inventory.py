"""Rastreabilidade: lotes (com validade) e números de série."""
from ..extensions import db
from ..utils.datas import agora
from .product import QTD

STATUS_SERIE = {"em_estoque": "Em estoque", "saiu": "Saiu do estoque"}


class Lote(db.Model):
    __tablename__ = "lotes"
    __table_args__ = (
        db.UniqueConstraint("product_id", "numero", name="uq_lote_produto_numero"),
        db.Index("ix_lote_validade", "validade"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False, index=True)
    numero = db.Column(db.String(50), nullable=False)
    validade = db.Column(db.Date)
    # Saldo do lote: alterado apenas pelo inventory_service.
    quantidade = db.Column(QTD, nullable=False, default=0)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    produto = db.relationship("Product", back_populates="lotes")
    movimentacoes = db.relationship("InventoryMovement", back_populates="lote", lazy="dynamic")


class SerialNumber(db.Model):
    __tablename__ = "numeros_serie"
    __table_args__ = (db.UniqueConstraint("product_id", "numero", name="uq_serie_produto_numero"),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False, index=True)
    numero = db.Column(db.String(80), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="em_estoque")
    entrada_mov_id = db.Column(db.Integer, db.ForeignKey("movimentacoes.id"))
    saida_mov_id = db.Column(db.Integer, db.ForeignKey("movimentacoes.id"))
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    produto = db.relationship("Product")
    entrada = db.relationship("InventoryMovement", foreign_keys=[entrada_mov_id])
    saida = db.relationship("InventoryMovement", foreign_keys=[saida_mov_id])

    @property
    def status_nome(self):
        return STATUS_SERIE.get(self.status, self.status)
