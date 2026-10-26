"""Conversão de valores digitados pelo usuário (padrão brasileiro)."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class ValorInvalido(ValueError):
    pass


def parse_decimal(valor, campo="valor", obrigatorio=True, casas=None):
    """Converte "1.234,56", "1234,56" ou "1234.56" em Decimal.

    Se houver vírgula, ela é o separador decimal e os pontos são de milhar.
    Sem vírgula, o ponto é tratado como separador decimal.
    """
    if valor is None or (isinstance(valor, str) and valor.strip() == ""):
        if obrigatorio:
            raise ValorInvalido(f"Informe {campo}.")
        return None
    if isinstance(valor, (int, float, Decimal)):
        numero = Decimal(str(valor))
    else:
        texto = valor.strip().replace("R$", "").replace(" ", "")
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        try:
            numero = Decimal(texto)
        except InvalidOperation:
            raise ValorInvalido(f"{campo.capitalize()} inválido(a). Use apenas números, por exemplo: 10,50.")
    if not numero.is_finite():
        raise ValorInvalido(f"{campo.capitalize()} inválido(a).")
    if casas is not None:
        numero = numero.quantize(Decimal(1).scaleb(-casas))
    return numero


def parse_date(valor, campo="data", obrigatorio=False):
    """Aceita AAAA-MM-DD (campo date do HTML) ou DD/MM/AAAA."""
    if valor is None or (isinstance(valor, str) and valor.strip() == ""):
        if obrigatorio:
            raise ValorInvalido(f"Informe {campo}.")
        return None
    if isinstance(valor, date):
        return valor
    texto = valor.strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValorInvalido(f"{campo.capitalize()} inválida. Use o formato DD/MM/AAAA.")


def parse_int(valor, padrao=None):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def parse_bool(valor) -> bool:
    return str(valor).lower() in ("1", "true", "on", "sim", "yes")
