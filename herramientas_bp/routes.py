from flask import Blueprint, render_template
from extensions import db

# Creamos el Blueprint
# El primer argumento 'herramientas' es el nombre del Blueprint.
# __name__ ayuda a Flask a localizar plantillas y archivos estáticos.
# template_folder='../templates/herramientas' le dice dónde buscar las plantillas para este blueprint
# (asumiendo que templates está al mismo nivel que herramientas_bp)
herramientas_bp = Blueprint('herramientas', __name__, template_folder='../templates/herramientas')

@herramientas_bp.route('/herramientas/') # La URL para esta página
def dashboard():
    # Más adelante, aquí verificaremos si el usuario está logueado
    # y mostraremos las herramientas disponibles.
    return render_template('dashboard_herramientas.html', titulo_pagina="Panel de Herramientas")