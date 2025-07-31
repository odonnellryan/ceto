from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, FileField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(max=80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Confirm Password',
                              validators=[DataRequired(), EqualTo('password')])


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')


class GreenUploadForm(FlaskForm):
    file = FileField('Green File (PDF/Excel)')
    manual_data = TextAreaField('Manual Entry')


class TastingNoteForm(FlaskForm):
    notes = TextAreaField('Tasting Notes', validators=[DataRequired()])
