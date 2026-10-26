def registrar_blueprints(app):
    from .alerts import bp as alerts_bp
    from .auth import bp as auth_bp
    from .dashboard import bp as dashboard_bp
    from .inventory import bp as inventory_bp
    from .products import bp as products_bp
    from .reports import bp as reports_bp
    from .sales import bp as sales_bp
    from .admin import bp as admin_bp

    for bp in (auth_bp, dashboard_bp, products_bp, inventory_bp, sales_bp, alerts_bp, reports_bp, admin_bp):
        app.register_blueprint(bp)
