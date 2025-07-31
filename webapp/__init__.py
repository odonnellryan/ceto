from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate

# Initialize extensions

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'changeme'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    from .models import User
    login_manager.login_view = 'auth.login'

    from .views.auth import auth_bp
    from .views.main import main_bp
    from .views.green import green_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(green_bp)

    # Flask-Admin setup
    from flask_admin import Admin
    from flask_admin.contrib.sqla import ModelView
    admin = Admin(app, name='Ceto Admin', template_mode='bootstrap4')
    from .models import GreenData, TastingNote, Suggestion, SuggestionVote
    admin.add_view(ModelView(User, db.session))
    admin.add_view(ModelView(GreenData, db.session))
    admin.add_view(ModelView(TastingNote, db.session))
    admin.add_view(ModelView(Suggestion, db.session))
    admin.add_view(ModelView(SuggestionVote, db.session))

    return app
