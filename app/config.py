"""Configurações da aplicação.

Os parâmetros de negócio (limites da Curva ABC, janelas de validade etc.) ficam
centralizados em ``DEFAULT_SETTINGS``. Eles podem ser alterados pelo
administrador na tela "Configurações" (valores gravados na tabela
``configuracoes``), sem precisar mexer no código.
"""
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

# Parâmetros de negócio padrão (chave -> (valor padrão, tipo, descrição))
DEFAULT_SETTINGS = {
    "nome_loja": ("Minha Loja", str, "Nome do comércio exibido no sistema"),
    "abc_limite_a": (80, int, "Curva ABC: % acumulado do faturamento que define a classe A"),
    "abc_limite_b": (95, int, "Curva ABC: % acumulado do faturamento que define o fim da classe B"),
    "abc_periodo_dias": (90, int, "Curva ABC: período padrão de vendas analisado (dias)"),
    "validade_alerta_dias": (30, int, "Alertar produtos que vencem em até N dias"),
    "validade_critico_dias": (7, int, "Considerar urgente quando vence em até N dias"),
    "dashboard_periodo_dias": (30, int, "Período padrão das vendas no painel (dias)"),
}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-chave-insegura-apenas-para-demonstracao"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + os.path.join(INSTANCE_DIR, "estoque.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    WTF_CSRF_TIME_LIMIT = None  # o token vale enquanto a sessão estiver ativa
    ITENS_POR_PAGINA = 20


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "teste"


CONFIGS = {"default": Config, "testing": TestConfig}
