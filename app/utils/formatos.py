"""Filtros de exibição no padrão brasileiro (usados nos templates)."""
from decimal import Decimal


def _milhar(texto_inteiro: str) -> str:
    negativo = texto_inteiro.startswith("-")
    digitos = texto_inteiro.lstrip("-")
    grupos = []
    while len(digitos) > 3:
        grupos.insert(0, digitos[-3:])
        digitos = digitos[:-3]
    grupos.insert(0, digitos)
    return ("-" if negativo else "") + ".".join(grupos)


def numero_br(valor, casas=2) -> str:
    if valor is None:
        valor = 0
    valor = Decimal(str(valor)).quantize(Decimal(1).scaleb(-casas))
    texto = f"{valor:.{casas}f}"
    inteiro, _, frac = texto.partition(".")
    return _milhar(inteiro) + ("," + frac if casas else "")


def brl(valor) -> str:
    return "R$ " + numero_br(valor, 2)


def qtd(valor) -> str:
    """Quantidade sem zeros desnecessários: 10 -> "10", 1.500 -> "1,5"."""
    if valor is None:
        valor = 0
    valor = Decimal(str(valor)).quantize(Decimal("0.001"))
    texto = numero_br(valor, 3).rstrip("0").rstrip(",")
    return texto if texto not in ("", "-0") else "0"


def pct(valor, casas=1) -> str:
    return numero_br(valor or 0, casas) + "%"


def data_br(valor) -> str:
    return valor.strftime("%d/%m/%Y") if valor else "—"


def datahora_br(valor) -> str:
    return valor.strftime("%d/%m/%Y %H:%M") if valor else "—"


def registrar_filtros(app):
    app.jinja_env.filters.update(
        brl=brl, qtd=qtd, pct=pct, data=data_br, datahora=datahora_br, numero=numero_br
    )
