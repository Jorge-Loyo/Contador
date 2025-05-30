from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required # Añade login_required

# Asegúrate de que estas importaciones sean correctas según tu estructura
# Si app.py está un nivel arriba de auth_bp/
import sys
sys.path.append("..") # Añade el directorio padre (Contador/) al path para encontrar app y models

from extensions import db 
from models import User
from forms import RegistrationForm, LoginForm #LoginForm se usará aquí

auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('herramientas.dashboard')) 

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('¡Tu cuenta ha sido creada! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la cuenta. Es posible que el usuario o email ya existan.', 'danger')
            # app.logger.error(f"Error en registro: {e}", exc_info=True) # Descomenta si tienes app.logger configurado y accesible
            print(f"Error en registro: {e}")
    return render_template('register.html', title='Registrarse', form=form)

# --- NUEVA RUTA DE LOGIN ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('herramientas.dashboard')) # O a donde quieras que vayan los ya logueados

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first() # Busca al usuario
        # Podrías permitir login con email también:
        # user_by_email = User.query.filter_by(email=form.username.data).first()
        # user = user_by_username if user_by_username else user_by_email

        if user and user.check_password(form.password.data): # Verifica usuario y contraseña
            login_user(user, remember=form.remember_me.data) # Inicia sesión con Flask-Login
            flash('¡Has iniciado sesión correctamente!', 'success')

            # Redirigir a la página que intentaba acceder, o al dashboard de herramientas
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('herramientas.dashboard'))
        else:
            flash('Login incorrecto. Por favor, verifica tu nombre de usuario y contraseña.', 'danger')

    return render_template('login.html', title='Iniciar Sesión', form=form)

@auth_bp.route('/logout')
@login_required # Solo usuarios logueados pueden desloguearse
def logout():
    logout_user() # Desloguea al usuario con Flask-Login
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('auth.login')) # O a la página principal 'h