from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from dotenv import load_dotenv

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)

    from app.config import Config
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY must be set in the environment or app config.')
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        raise RuntimeError(
            'SQLALCHEMY_DATABASE_URI must be set in the environment or app config.'
        )

    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu.'
    login_manager.login_message_category = 'warning'

    from app.models.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Context processor
    from datetime import datetime
    @app.context_processor
    def inject_globals():
        return {'now': datetime.now().strftime('%d %B %Y, %H:%M')}

    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))

    # Register blueprints
    from app.controllers.auth_controller import auth_bp
    app.register_blueprint(auth_bp)

    from app.controllers.obat_controller import obat_bp
    app.register_blueprint(obat_bp, url_prefix='/obat')

    from app.controllers.clustering_controller import clustering_bp
    app.register_blueprint(clustering_bp, url_prefix='/clustering')

    from app.controllers.eoq_controller import eoq_bp
    app.register_blueprint(eoq_bp, url_prefix='/eoq')

    from app.controllers.dashboard_controller import dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.controllers.laporan_controller import laporan_bp
    app.register_blueprint(laporan_bp, url_prefix='/laporan')

    from app.controllers.alert_controller import alert_bp
    app.register_blueprint(alert_bp)

    from app.models import models  # noqa: ensure tables are registered

    return app