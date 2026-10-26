from ..extensions import db
from ..utils.datas import agora
from .product import DINHEIRO, QTD

FORMAS_PAGAMENTO = {
    "dinheiro": "Dinheiro",
    "pix": "Pix",
    "debito": "Cartão de débito",
    "credito": "Cartão de crédito",
    "fiado": "Fiado / a prazo",
    "outro": "Outro",
}


class Sale(db.Model):
    __tablename__ = "vendas"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False, default=agora, index=True)
    valor_total = db.Column(DINHEIRO, nullable=False, default=0)
    forma_pagamento = db.Column(db.String(20))
    observacao = db.Column(db.String(255))

    usuario = db.relationship("User")
    itens = db.relationship("SaleItem", back_populates="venda", cascade="all, delete-orphan")

    @property
    def forma_pagamento_nome(self):
        return FORMAS_PAGAMENTO.get(self.forma_pagamento or "", "—")


class SaleItem(db.Model):
    __tablename__ = "venda_itens"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False, index=True)
    quantidade = db.Column(QTD, nullable=False)
    preco_unitario = db.Column(DINHEIRO, nullable=False)
    subtotal = db.Column(DINHEIRO, nullable=False)

    venda = db.relationship("Sale", back_populates="itens")
    produto = db.relationship("Product")
