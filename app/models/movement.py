from ..extensions import db
from ..utils.datas import agora
from .product import DINHEIRO, QTD

TIPOS_ENTRADA = {
    "compra": "Compra (fornecedor)",
    "devolucao": "Devolução de cliente",
    "ajuste_positivo": "Ajuste positivo (contagem)",
    "outros": "Outros",
}

TIPOS_SAIDA = {
    "venda": "Venda",
    "perda": "Perda / quebra / vencido",
    "consumo": "Consumo interno",
    "devolucao": "Devolução ao fornecedor",
    "ajuste_negativo": "Ajuste negativo (contagem)",
    "outros": "Outros",
}

NATUREZAS = {"entrada": "Entrada", "saida": "Saída"}


class InventoryMovement(db.Model):
    """Registro imutável de toda alteração de saldo (auditoria)."""

    __tablename__ = "movimentacoes"
    __table_args__ = (
        db.Index("ix_mov_produto_data", "product_id", "data_hora"),
        db.Index("ix_mov_data", "data_hora"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    natureza = db.Column(db.String(10), nullable=False)  # entrada | saida
    tipo = db.Column(db.String(30), nullable=False, index=True)
    quantidade = db.Column(QTD, nullable=False)  # sempre positiva
    saldo_apos = db.Column(QTD, nullable=False)
    lote_id = db.Column(db.Integer, db.ForeignKey("lotes.id"), index=True)
    numero_serie = db.Column(db.Text)  # números de série envolvidos (separados por vírgula)
    validade = db.Column(db.Date)
    valor_unitario = db.Column(DINHEIRO)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    data_hora = db.Column(db.DateTime, nullable=False, default=agora)
    observacao = db.Column(db.String(255))
    sale_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), index=True)

    produto = db.relationship("Product")
    usuario = db.relationship("User")
    lote = db.relationship("Lote", back_populates="movimentacoes")

    @property
    def tipo_nome(self) -> str:
        tipos = TIPOS_ENTRADA if self.natureza == "entrada" else TIPOS_SAIDA
        return tipos.get(self.tipo, self.tipo)

    @property
    def quantidade_assinada(self):
        return self.quantidade if self.natureza == "entrada" else -self.quantidade
