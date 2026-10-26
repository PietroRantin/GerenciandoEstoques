"""Leitura e gravação centralizada dos parâmetros de negócio."""
from ..config import DEFAULT_SETTINGS
from ..extensions import db
from ..models import Setting
from .errors import RegraNegocioError


def get(chave: str):
    padrao, tipo, _ = DEFAULT_SETTINGS[chave]
    registro = db.session.get(Setting, chave)
    if registro is None:
        return padrao
    try:
        return tipo(registro.valor)
    except (TypeError, ValueError):
        return padrao


def todos() -> dict:
    return {chave: get(chave) for chave in DEFAULT_SETTINGS}


def salvar(valores: dict) -> None:
    novos = {}
    for chave, (padrao, tipo, descricao) in DEFAULT_SETTINGS.items():
        if chave not in valores:
            continue
        bruto = str(valores[chave]).strip()
        if tipo is int:
            try:
                valor = int(bruto)
            except ValueError:
                raise RegraNegocioError(f"Valor inválido para \"{descricao}\". Use um número inteiro.")
            if valor < 0:
                raise RegraNegocioError(f"\"{descricao}\" não pode ser negativo.")
        else:
            valor = bruto or padrao
        novos[chave] = valor

    a = novos.get("abc_limite_a", get("abc_limite_a"))
    b = novos.get("abc_limite_b", get("abc_limite_b"))
    if not (0 < a < b <= 100):
        raise RegraNegocioError("Curva ABC: o limite da classe A deve ser menor que o da classe B, e ambos entre 1 e 100.")
    critico = novos.get("validade_critico_dias", get("validade_critico_dias"))
    alerta = novos.get("validade_alerta_dias", get("validade_alerta_dias"))
    if critico > alerta:
        raise RegraNegocioError("Validade: o prazo urgente deve ser menor ou igual ao prazo de alerta.")
    for chave in ("abc_periodo_dias", "dashboard_periodo_dias"):
        if chave in novos and novos[chave] < 1:
            raise RegraNegocioError("O período deve ser de pelo menos 1 dia.")

    for chave, valor in novos.items():
        registro = db.session.get(Setting, chave)
        if registro is None:
            db.session.add(Setting(chave=chave, valor=str(valor)))
        else:
            registro.valor = str(valor)
    db.session.commit()
