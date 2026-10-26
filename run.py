"""Ponto de entrada: `python run.py` inicia o sistema em http://localhost:5000

Na primeira execução, o banco é criado automaticamente pelas migrations.
Para carregar os dados de demonstração: `flask --app run seed` (ou `python -m seed.seed`).
"""
import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

app = create_app()


def preparar_banco():
    """Aplica as migrations pendentes (cria as tabelas na primeira execução)."""
    from flask_migrate import upgrade
    with app.app_context():
        upgrade()
        from app.models import User
        if User.query.count() == 0:
            from app.services.user_service import criar_usuario_inicial
            criar_usuario_inicial("Administrador", "admin@estoque.local", "admin123", "admin")
            print("Usuário inicial criado: admin@estoque.local / admin123 (troque a senha!)")


if __name__ == "__main__":
    preparar_banco()
    porta = int(os.environ.get("PORT") or 5000)
    print(f"Estoque Fácil rodando em http://localhost:{porta}")
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=porta, debug=os.environ.get("FLASK_DEBUG") == "1")
