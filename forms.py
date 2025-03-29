from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
# Import User model to check for existing users
try:
    # Assuming your models are defined correctly and accessible
    from models import User
except ImportError:
    # Handle case where models might not be importable yet,
    # though this shouldn't happen if structure is correct.
    User = None
    print("WARNING: Could not import User model in forms.py")


class RegistrationForm(FlaskForm):
    """Form for user registration."""
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Sign Up')

    # Custom validator to check if username already exists
    def validate_username(self, username):
        if User: # Check if User model was imported
            user = User.get_by_username(username.data)
            if user:
                raise ValidationError('That username is already taken. Please choose a different one.')

    # Custom validator to check if email already exists
    def validate_email(self, email):
         if User: # Check if User model was imported
            user = User.get_by_email(email.data)
            if user:
                raise ValidationError('That email is already registered. Please log in or use a different one.')


class LoginForm(FlaskForm):
    """Form for user login."""
    # Allow login with either username or email (we'll handle this in the route)
    # For simplicity now, let's stick to username
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me') # For "Remember Me" functionality
    submit = SubmitField('Login')