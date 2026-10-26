"""Estoque Fácil — sistema de gestão de estoque para pequenos comércios."""
import logging
import os

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import SQLAlchemyError

from .config import CONFIGS, INSTANCE_DIR
from .extensions import csrf, db, login_manager, migrate
from .utils.formatos import registrar_filtros

__version__ = "1.0.0"


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_path=INSTANCE_DIR)
    app.config.from_object(CONFIGS[config_name or os.environ.get("APP_CONFIG", "default")])
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(app.root_path), "migrations"),
                     render_as_batch=True)
    csrf.init_app(app)
    login_manager.init_app(app)
    registrar_filtros(app)

    from . import models  # noqa: F401  (registra as tabelas)
    from .models import User

    @login_manager.user_loader
    def carregar_usuario(user_id):
        usuario = db.session.get(User, int(user_id))
        return usuario if usuario and usuario.ativo else None

    from .routes import registrar_blueprints
    registrar_blueprints(app)
    _registrar_erros(app)
    _registrar_contexto(app)
    _registrar_comandos(app)
    return app


def _registrar_contexto(app):
    from .models.alert import Alert
    from .services import settings_service

    @app.context_processor
    def contexto_global():
        from flask_login import current_user
        dados = {"versao": __version__}
        if current_user.is_authenticated:
            try:
                dados["nome_loja"] = settings_service.get("nome_loja")
                dados["total_alertas"] = Alert.query.filter_by(resolvido=False).count()
            except SQLAlchemyError:
                db.session.rollback()
        return dados


def _registrar_erros(app):
    @app.errorhandler(403)
    def proibido(_):
        return render_template("erro.html", codigo=403, titulo="Acesso não permitido",
                               mensagem="Seu perfil não tem permissão para esta página. "
                                        "Peça ajuda a um administrador."), 403

    @app.errorhandler(404)
    def nao_encontrado(_):
        return render_template("erro.html", codigo=404, titulo="Página não encontrada",
                               mensagem="O endereço não existe ou o registro foi removido."), 404

    @app.errorhandler(CSRFError)
    def csrf_invalido(_):
        flash("Sua sessão expirou ou o formulário ficou muito tempo aberto. Confira os dados e envie novamente.",
              "warning")
        return redirect(request.referrer or url_for("dashboard.index"))

    @app.errorhandler(SQLAlchemyError)
    def erro_banco(exc):
        db.session.rollback()
        app.logger.exception("Erro de banco de dados: %s", exc)
        return render_template("erro.html", codigo=500, titulo="Não foi possível salvar",
                               mensagem="Ocorreu um problema ao acessar os dados. Tente novamente. "
                                        "Se o problema continuar, reinicie o sistema."), 500

    @app.errorhandler(500)
    def erro_interno(exc):
        db.session.rollback()
        logging.getLogger(__name__).exception("Erro interno: %s", exc)
        return render_template("erro.html", codigo=500, titulo="Algo deu errado",
                               mensagem="Ocorreu um erro inesperado. Nenhum dado foi perdido. "
                                        "Volte para a página anterior e tente novamente."), 500


def _registrar_comandos(app):
    import click

    @app.cli.command("seed")
    @click.option("--manter", is_flag=True, help="Não apaga os dados existentes.")
    def seed_command(manter):
        """Popula o banco com dados de demonstração."""
        from seed.seed import popular_banco
        popular_banco(resetar=not manter)
        click.echo("Dados de demonstração criados.")

    @app.cli.command("criar-admin")
    @click.option("--nome", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--senha", prompt=True, hide_input=True, confirmation_prompt=True)
    def criar_admin(nome, email, senha):
        """Cria um usuário administrador."""
        from .services.user_service import criar_usuario_inicial
        criar_usuario_inicial(nome, email, senha, "admin")
        click.echo(f"Administrador {email} pronto.")

    @app.cli.command("verificar-saldos")
    def verificar_saldos():
        """Confere se o saldo de cada produto bate com o histórico de movimentações."""
        from .models import Product
        from .services.inventory_service import recalcular_saldo
        divergentes = 0
        for produto in Product.query.all():
            calculado = recalcular_saldo(produto.id)
            if calculado != produto.estoque_atual:
                divergentes += 1
                click.echo(f"DIVERGENTE: {produto.sku} saldo={produto.estoque_atual} histórico={calculado}")
        click.echo("Todos os saldos conferem com o histórico." if not divergentes
                   else f"{divergentes} produto(s) divergente(s).")
