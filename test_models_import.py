# test_models_import.py
print("Iniciando prueba de importación...")

# Simulamos la parte mínima de app.py necesaria para inicializar db
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv() # Carga .env si existe, para que DB_... estén disponibles
print("dotenv cargado (si existía .env).")

app_test = Flask(__name__)
app_test.config['SECRET_KEY'] = 'testkey' # Necesario para algunas configuraciones

# Usar configuración de SQLite para esta prueba, para simplicidad
basedir_test = os.path.abspath(os.path.dirname(__file__))
app_test.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir_test, 'test_import_temp_db.sqlite')
app_test.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
print(f"Usando DB URI para prueba: {app_test.config['SQLALCHEMY_DATABASE_URI']}")

# Definimos 'db' en el scope de este script de prueba
# para que models.py (que hace 'from app import db' o similar) lo encuentre.
# ¡ESTO ES SOLO PARA LA PRUEBA! En tu app.py real, 'db' ya está definido.
# El truco aquí es que 'models.py' espera importar 'db' desde un módulo llamado 'app'.
# Así que, para esta prueba, necesitamos que 'db' esté en el módulo que se está ejecutando
# si 'models.py' hace 'from __main__ import db' o si cambiamos 'models.py' temporalmente.

# Mejor aún, vamos a asegurarnos de que 'db' esté definido antes de intentar importar 'User'
# y que 'models.py' importe 'db' del 'app.py' real.
# Lo que este test realmente prueba es si 'models.py' tiene un error INTERNO o si 'User' está bien definido.

print("Intentando importar 'db' y 'User' como lo haría app.py...")
try:
    # Primero, asegurémonos de que 'db' se pueda crear en el contexto de 'app'
    # Esto simula la parte de tu app.py real:
    # app = Flask(...)
    # ...config...
    # db = SQLAlchemy(app) <--- Este es el 'db' que models.py debe importar

    # Para que models.py pueda hacer 'from app import db', tenemos que
    # asegurarnos que app.py no tenga un error que impida definir 'db'.
    # Ya que estamos en un script separado, no podemos importar 'db' desde 'app.py' directamente
    # de la misma forma que lo hace models.py cuando app.py es el script principal.

    # Lo que SÍ podemos probar es si hay un error DENTRO de models.py:
    print("Importando 'models' directamente para ver si define 'User'...")
    import models # Intenta importar el módulo models.py

    if hasattr(models, 'User'):
        User = models.User
        print(f"ÉXITO: 'User' encontrado en el módulo 'models': {User}")
        # Intentemos una operación simple que use db a través de User
        # Para esto, 'models.User' necesita estar vinculado a una instancia de db
        # que esté vinculada a una app.
        # Esta prueba de importación directa es más para ver si 'User' se DEFINE.
    else:
        print("FALLO: El módulo 'models' se importó, pero no contiene un atributo 'User'.")

except ImportError as e:
    print(f"FALLO AL IMPORTAR 'models' o 'User' desde 'models': {e}")
    print("Esto podría ser un problema en models.py o un problema de importación circular más complejo.")
except Exception as e_other:
    print(f"FALLO: Ocurrió otro error durante la prueba de importación: {e_other}")

print("Prueba de importación finalizada.")