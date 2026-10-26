from decimal import Decimal

from ..extensions import db
from ..utils.datas import agora

UNIDADES = {
    "un": "Unidade (un)",
    "kg": "Quilo (kg)",
    "g": "Grama (g)",
    "l": "Litro (l)",
    "ml": "Mililitro (ml)",
    "cx": "Caixa (cx)",
    "pct": "Pacote (pct)",
    "dz": "Dúzia (dz)",
    "fd": "Fardo (fd)",
}

QTD = db.Numeric(12, 3)
DINHEIRO = db.Numeric(12, 2)


class Product(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), nullable=False, unique=True, index=True)
    codigo_barras = db.Column(db.String(50), unique=True, index=True)
    nome = db.Column(db.String(120), nullable=False, index=True)
    descricao = db.Column(db.Text)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), index=True)
    unidade = db.Column(db.String(10), nullable=False, default="un")
    preco_custo = db.Column(DINHEIRO, nullable=False, default=0)
    preco_venda = db.Column(DINHEIRO, nullable=False, default=0)
    # Saldo atual: NÃO é editável pelo cadastro. É alterado exclusivamente pelo
    # inventory_service, na mesma transação em que a movimentação é gravada.
    # Funciona como um "cache" do somatório das movimentações, permitindo a
    # consulta de saldo instantânea (ver inventory_service.recalcular_saldo).
    estoque_atual = db.Column(QTD, nullable=False, default=0)
    estoque_minimo = db.Column(QTD, nullable=False, default=0)
    estoque_maximo = db.Column(QTD, nullable=False, default=0)
    ponto_pedido = db.Column(QTD, nullable=False, default=0)
    controla_lote = db.Column(db.Boolean, nullable=False, default=False)
    controla_validade = db.Column(db.Boolean, nullable=False, default=False)
    controla_serie = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=agora, onupdate=agora)

    categoria = db.relationship("Category", back_populates="produtos")
    lotes = db.relationship("Lote", back_populates="produto", lazy="dynamic")

    # ---- Regras de situação (somente leitura) ---------------------------
    @property
    def usa_lote(self) -> bool:
        """Produtos com lote ou validade têm o saldo distribuído em lotes."""
        return bool(self.controla_lote or self.controla_validade)

    @property
    def sem_estoque(self) -> bool:
        return Decimal(self.estoque_atual or 0) <= 0

    @property
    def precisa_reposicao(self) -> bool:
        return Decimal(self.estoque_atual or 0) <= Decimal(self.ponto_pedido or 0)

    @property
    def acima_maximo(self) -> bool:
        maximo = Decimal(self.estoque_maximo or 0)
        return maximo > 0 and Decimal(self.estoque_atual or 0) > maximo

    @property
    def quantidade_sugerida(self) -> Decimal:
        """Sugestão de compra = estoque máximo - estoque atual."""
        maximo = Decimal(self.estoque_maximo or 0)
        atual = Decimal(self.estoque_atual or 0)
        if maximo > 0:
            return max(maximo - atual, Decimal(0))
        # Sem máximo definido: repor até 2x o ponto de pedido
        return max(Decimal(self.ponto_pedido or 0) * 2 - atual, Decimal(0))

    @property
    def valor_estoque(self) -> Decimal:
        return Decimal(self.estoque_atual or 0) * Decimal(self.preco_custo or 0)

    @property
    def situacao(self) -> tuple[str, str]:
        """(rótulo, cor bootstrap)"""
        if not self.ativo:
            return ("Inativo", "secondary")
        if self.sem_estoque:
            return ("Sem estoque", "danger")
        if self.precisa_reposicao:
            return ("Repor", "warning")
        if self.acima_maximo:
            return ("Acima do máximo", "info")
        return ("Normal", "success")

    @property
    def margem(self):
        venda = Decimal(self.preco_venda or 0)
        if venda <= 0:
            return None
        return (venda - Decimal(self.preco_custo or 0)) / venda * 100
