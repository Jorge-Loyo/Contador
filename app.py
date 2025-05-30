# -----------------------------------------------------------------------------
# SECCIÓN 1: IMPORTACIONES
# -----------------------------------------------------------------------------
import os
import io
import time
from decimal import Decimal, getcontext, InvalidOperation
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required # UserMixin se usa en models.py
from dotenv import load_dotenv
from extensions import db, login_manager

# --- Cargar variables de entorno desde .env PRIMERO ---
load_dotenv()

# -----------------------------------------------------------------------------
# SECCIÓN 2: CREACIÓN DE INSTANCIAS DE EXTENSIONES (SIN APP AÚN)
# -----------------------------------------------------------------------------
# Crea las instancias de las extensiones aquí, ANTES de crear 'app'
# y ANTES de que 'models.py' o los blueprints intenten importarlas.
#db = SQLAlchemy()
#login_manager = LoginManager()
# login_manager.login_view y otros atributos se configurarán después de init_app

# Variables globales para rastrear si los módulos se cargaron
MODELS_DISPONIBLES = False
User = None # Definir User globalmente, se asignará después de importar models

# -----------------------------------------------------------------------------
# SECCIÓN 3: CREACIÓN Y CONFIGURACIÓN DE LA APLICACIÓN FLASK
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'UNA_CLAVE_SECRETA_MUY_FUERTE_PARA_DESARROLLO_LOCAL_CAMBIAME')

DB_USERNAME = os.environ.get('DB_USERNAME_PA')
# ... (resto de tu config de DB_PASSWORD, DB_HOST, DB_NAME) ...
DB_PASSWORD = os.environ.get('DB_PASSWORD_PA')
DB_HOST = os.environ.get('DB_HOST_PA')
DB_NAME = os.environ.get('DB_NAME_PA')


if all([DB_USERNAME, DB_PASSWORD, DB_HOST, DB_NAME]):
    app.config['SQLALCHEMY_DATABASE_URI'] = \
        f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
else:
    print("ADVERTENCIA: Variables de entorno para MySQL no configuradas. Usando SQLite local ('local_db.sqlite').")
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'local_db.sqlite')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- INICIALIZAR EXTENSIONES CON LA APP ---
db.init_app(app) # <--- Usa la instancia db importada de extensions.py
login_manager.init_app(app) # <--- Usa la instancia login_manager importada
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info"

# -----------------------------------------------------------------------------
# SECCIÓN 4: IMPORTACIÓN DE MODELOS Y CONFIGURACIÓN DE USER LOADER
# -----------------------------------------------------------------------------
# Ahora 'models.py' puede hacer 'from app import db' de forma segura,
# porque 'db' ya existe como objeto SQLAlchemy (aunque se vincule a 'app' completamente con init_app).
try:
    from models import User as UserModel # models.py ahora importará db de extensions.py
    User = UserModel
    MODELS_DISPONIBLES = True

    @login_manager.user_loader
    def load_user(user_id):
        if User:
            return User.query.get(int(user_id))
        return None
except ImportError as e:
    MODELS_DISPONIBLES = False
    print(f"ADVERTENCIA: No se pudo importar el modelo User: {e}.")
    @login_manager.user_loader
    def load_user(user_id): # pragma: no cover
        print("ADVERTENCIA: load_user llamado, pero el modelo User no está disponible.")
        return None

# -----------------------------------------------------------------------------
# SECCIÓN 5: IMPORTACIÓN Y REGISTRO DE BLUEPRINTS
# -----------------------------------------------------------------------------
# Los blueprints pueden ahora importar 'db' de 'app' y 'User' de 'models' de forma segura.
try:
    from herramientas_bp.routes import herramientas_bp
    app.register_blueprint(herramientas_bp)
    print("INFO: Blueprint 'herramientas_bp' registrado.")
except ImportError as e:
    print(f"Advertencia: No se pudo importar o registrar 'herramientas_bp': {e}.")

try:
    from auth_bp.routes import auth_bp
    app.register_blueprint(auth_bp)
    print("INFO: Blueprint 'auth_bp' registrado.")
except ImportError as e:
    print(f"Advertencia: No se pudo importar o registrar 'auth_bp': {e}.")



# -----------------------------------------------------------------------------
# SECCIÓN 6: DEFINICIONES DE CLASES AUXILIARES (si las hay)
# -----------------------------------------------------------------------------
class CombinacionSolver:
    # ... (Tu clase CombinacionSolver completa aquí sin cambios internos) ...
    def __init__(self, items_original_lista, monto_objetivo_str, time_limit_seconds=30):
        self.items_procesados = []
        try:
            self.monto_objetivo = Decimal(monto_objetivo_str)
        except InvalidOperation:
            raise ValueError("El monto objetivo ingresado no es un número válido.")

        self.time_limit_seconds = time_limit_seconds
        self.start_time = 0
        self.time_limit_exceeded_flag = False 

        self.best_sum_found = Decimal('0')
        self.best_selection_items_data = [] 

        if self.monto_objetivo <= 0:
            return

        for idx, data_row in enumerate(items_original_lista): 
            try:
                item_id = data_row[0]
                monto_val_str = str(data_row[1]) 
                monto = Decimal(monto_val_str)
                if monto <= Decimal('0'): 
                    continue
                self.items_procesados.append({
                    'id': item_id,
                    'monto': monto,
                })
            except Exception as e:
                print(f"WARN [CombinacionSolver]: Item inválido omitido: {data_row} debido a {e}")
                continue
        
        self.items_procesados.sort(key=lambda x: x['monto'], reverse=True)
        self.num_items = len(self.items_procesados)
        
        self.remaining_sum_array = [Decimal('0')] * (self.num_items + 1)
        if self.num_items > 0:
            current_remaining_sum = Decimal('0')
            for i in range(self.num_items - 1, -1, -1):
                current_remaining_sum += self.items_procesados[i]['monto']
                self.remaining_sum_array[i] = current_remaining_sum
        
    def _solve_recursive(self, index, current_sum, current_selection_data):
        if self.time_limit_exceeded_flag: return
        if time.time() - self.start_time > self.time_limit_seconds:
            self.time_limit_exceeded_flag = True
            print(f"INFO [CombinacionSolver]: Límite de tiempo de {self.time_limit_seconds}s alcanzado.")
            return
        if current_sum <= self.monto_objetivo and current_sum > self.best_sum_found:
            self.best_sum_found = current_sum
            self.best_selection_items_data = list(current_selection_data) 
        if index == self.num_items: return
        if current_sum + self.remaining_sum_array[index] < self.best_sum_found: return
        item_actual = self.items_procesados[index]
        if current_sum + item_actual['monto'] <= self.monto_objetivo: 
            current_selection_data.append(item_actual)
            self._solve_recursive(index + 1, current_sum + item_actual['monto'], current_selection_data)
            current_selection_data.pop() 
            if self.time_limit_exceeded_flag: return
        self._solve_recursive(index + 1, current_sum, current_selection_data)

    def find_combination(self):
        if self.monto_objetivo <= 0 or not self.items_procesados:
            return [], Decimal('0'), self.monto_objetivo, self.time_limit_exceeded_flag
        self.start_time = time.time()
        self.time_limit_exceeded_flag = False 
        self.best_sum_found = Decimal('0')
        self.best_selection_items_data = []
        self._solve_recursive(0, Decimal('0'), [])
        final_combination_output = []
        for item_data in self.best_selection_items_data:
            final_combination_output.append((item_data['id'], item_data['monto']))
        elapsed_time = time.time() - self.start_time
        print(f"INFO [CombinacionSolver]: Búsqueda completada en {elapsed_time:.2f}s. Mejor suma: {self.best_sum_found}")
        if self.time_limit_exceeded_flag:
            print("WARN [CombinacionSolver]: La búsqueda fue terminada por límite de tiempo...")
        return final_combination_output, self.best_sum_found, self.monto_objetivo, self.time_limit_exceeded_flag

# -----------------------------------------------------------------------------
# SECCIÓN 7: RUTAS PRINCIPALES DE LA APLICACIÓN (app.py)
# -----------------------------------------------------------------------------
@app.route('/')
def home():
    return render_template('home.html', titulo_pagina="Bienvenido a Agilize Soluciones")

@app.route('/calculador', methods=['GET', 'POST'])
@login_required 
def calculador():
    # ... (Tu lógica de la ruta /calculador) ...
    titulo_actual = "Calculador: Comparador de Montos Excel" 
    if request.method == 'POST':
        if 'excel_file' in request.files:
            file = request.files['excel_file']
            if file.filename == '':
                return render_template('calculador.html', error_excel="No se seleccionó ningún archivo.", titulo_pagina=titulo_actual)
            if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
                try:
                    file_stream = io.BytesIO(file.read())
                    df = pd.read_excel(file_stream, engine='openpyxl')
                    file_stream.close() 
                    column_id_name = None; column_monto_name = None
                    possible_id_cols = ['ID', 'Id', 'id', 'Comprobante', 'COMPROBANTE', 'Numero', 'Número']
                    possible_monto_cols = ['Monto', 'MONTO', 'Importe', 'IMPORTE', 'Valor', 'VALOR', 'Total', 'TOTAL']
                    for col_name_excel in df.columns:
                        if column_id_name is None and col_name_excel.strip().lower() in [p.lower() for p in possible_id_cols]: column_id_name = col_name_excel
                        if column_monto_name is None and col_name_excel.strip().lower() in [p.lower() for p in possible_monto_cols]: column_monto_name = col_name_excel
                        if column_id_name and column_monto_name: break
                    if not column_id_name or not column_monto_name:
                        return render_template('calculador.html', error_excel="Columnas ID/Monto no encontradas. Cols: " + ", ".join(df.columns), titulo_pagina=titulo_actual)
                    excel_data_list = []
                    for _, row in df.iterrows():
                        try:
                            id_val = str(row[column_id_name]); monto_val = str(row[column_monto_name]) 
                            Decimal(monto_val); excel_data_list.append([id_val, monto_val])
                        except (InvalidOperation, KeyError, ValueError) as e_row :
                            app.logger.warning(f"Omitiendo fila: ID='{row.get(column_id_name)}', Monto='{row.get(column_monto_name)}'. Error: {e_row}")
                    if not excel_data_list:
                         return render_template('calculador.html', error_excel="No se encontraron datos válidos de ID y Monto.", titulo_pagina=titulo_actual)
                    session['excel_data'] = excel_data_list; session['filename'] = file.filename
                    return redirect(url_for('calculador')) 
                except Exception as e:
                    app.logger.error(f"Error leyendo Excel: {e}", exc_info=True)
                    return render_template('calculador.html', error_excel=f"Error al leer Excel: {e}", titulo_pagina=titulo_actual)
            else:
                return render_template('calculador.html', error_excel="Formato de archivo no válido.", titulo_pagina=titulo_actual)
        elif 'monto_objetivo' in request.form and 'excel_data' in session:
            monto_objetivo_str = request.form['monto_objetivo']; items_excel = session['excel_data'] 
            time_limit_config = 30 
            try:
                solver = CombinacionSolver(items_excel, monto_objetivo_str, time_limit_seconds=time_limit_config)
                combinacion, suma_obtenida, monto_objetivo_decimal, time_exceeded = solver.find_combination()
                suma_obtenida_str_disp = f"{suma_obtenida:.2f}"; monto_objetivo_str_disp = f"{monto_objetivo_decimal:.2f}"
                combinacion_display = [(item_id, f"{monto_val:.2f}") for item_id, monto_val in combinacion]
                return render_template('calculador_results.html', combinacion=combinacion_display, suma_obtenida=suma_obtenida_str_disp, monto_objetivo=monto_objetivo_str_disp,filename=session.get('filename'),time_exceeded=time_exceeded,time_limit_config=time_limit_config,titulo_pagina="Resultados del Calculador") 
            except ValueError as e: 
                 app.logger.error(f"Error en solver: {e}", exc_info=True)
                 return render_template('calculador.html', excel_cargado=True,filename=session.get('filename'),error_monto=str(e), titulo_pagina=titulo_actual)
            except Exception as e_general:
                 app.logger.error(f"Error inesperado: {e_general}", exc_info=True)
                 return render_template('calculador.html', excel_cargado=True,filename=session.get('filename'),error_monto=f"Error inesperado: {e_general}", titulo_pagina=titulo_actual)
    excel_cargado = 'excel_data' in session; filename = session.get('filename') if excel_cargado else None
    return render_template('calculador.html', excel_cargado=excel_cargado, filename=filename, titulo_pagina=titulo_actual)

@app.route('/calculador/reset') 
@login_required 
def reset_calculador():
    session.pop('excel_data', None)
    session.pop('filename', None)
    return redirect(url_for('calculador')) 

# -----------------------------------------------------------------------------
# SECCIÓN 8: COMANDOS CLI (como init-db)
# -----------------------------------------------------------------------------
@app.cli.command("init-db")
def init_db_command():
    if not MODELS_DISPONIBLES or User is None:
        print("Error: Modelos de base de datos (User) no disponibles.")
        return
    try:
        with app.app_context(): # Importante para operaciones de DB fuera de una request
            db.create_all()
        print("Base de datos inicializada y tablas creadas.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# -----------------------------------------------------------------------------
# SECCIÓN 9: PROCESADOR DE CONTEXTO PARA PLANTILLAS
# -----------------------------------------------------------------------------
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# -----------------------------------------------------------------------------
# SECCIÓN 10: EJECUCIÓN PARA DESARROLLO LOCAL
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO) 
    app.run(debug=True)