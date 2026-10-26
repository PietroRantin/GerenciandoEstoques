class RegraNegocioError(Exception):
    """Erro de regra de negócio com mensagem pronta para o usuário final."""

    def __init__(self, mensagem: str, erros: dict | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.erros = erros or {}


class EstoqueInsuficienteError(RegraNegocioError):
    pass
