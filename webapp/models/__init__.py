from datetime import datetime
from flask_login import UserMixin
from .. import db, login_manager, bcrypt


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    karma = db.Column(db.Integer, default=0)
    registered_on = db.Column(db.DateTime, default=datetime.utcnow)

    greens = db.relationship('GreenData', backref='uploader', lazy=True)
    notes = db.relationship('TastingNote', backref='author', lazy=True)
    suggestions = db.relationship('Suggestion', backref='author', lazy=True)

    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class GreenData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    manual_data = db.Column(db.Text)
    parsed_data = db.Column(db.Text)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notes = db.relationship('TastingNote', backref='green', lazy=True)
    suggestions = db.relationship('Suggestion', backref='green', lazy=True)


class TastingNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    green_data_id = db.Column(db.Integer, db.ForeignKey('green_data.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Suggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    green_data_id = db.Column(db.Integer, db.ForeignKey('green_data.id'), nullable=True)
    suggestion_text = db.Column(db.Text, nullable=False)
    accepted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime)

    votes = db.relationship('SuggestionVote', backref='suggestion', lazy=True)


class SuggestionVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    suggestion_id = db.Column(db.Integer, db.ForeignKey('suggestion.id'))
    vote = db.Column(db.Integer, default=1)  # +1 or -1
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
