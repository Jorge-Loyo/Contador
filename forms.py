from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
# Necesitaremos importar el modelo User para validar si un usuario o email ya existe
# Asegúrate de que models.py y User estén definidos correctamente
# Esto podría causar una importación circular si models.py también importa algo de forms.py
# Si eso ocurre, la importación de User se puede mover dentro de los métodos validate_*.
# Por ahora, intentemos así:
from models import User 

class RegistrationForm(FlaskForm):
    username = StringField('Nombre de Usuario', 
                           validators=[DataRequired(message="El nombre de usuario es requerido."), 
                                       Length(min=4, max=25, message="Debe tener entre 4 y 25 caracteres.")])
    email = StringField('Correo Electrónico', 
                        validators=[DataRequired(message="El correo es requerido."), 
                                    Email(message="Correo electrónico no válido.")])
    password = PasswordField('Contraseña', 
                             validators=[DataRequired(message="La contraseña es requerida."), 
                                         Length(min=6, message="Debe tener al menos 6 caracteres.")])
    confirm_password = PasswordField('Confirmar Contraseña', 
                                     validators=[DataRequired(message="Confirma la contraseña."), 
                                                 EqualTo('password', message="Las contraseñas deben coincidir.")])
    submit = SubmitField('Registrarse')

    # Validadores personalizados para chequear si el username o email ya existen
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ese nombre de usuario ya está en uso. Por favor, elige otro.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Ese correo electrónico ya está registrado. Por favor, elige otro.')

class LoginForm(FlaskForm):
    username = StringField('Nombre de Usuario', 
                           validators=[DataRequired(message="El nombre de usuario es requerido.")])
    # Podrías usar 'email' para el login también si lo prefieres, ajustando la lógica
    # email = StringField('Correo Electrónico', validators=[DataRequired(), Email()]) 
    password = PasswordField('Contraseña', 
                             validators=[DataRequired(message="La contraseña es requerida.")])
    remember_me = BooleanField('Recuérdame')
    submit = SubmitField('Iniciar Sesión')  