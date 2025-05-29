import os
import io
import time
from decimal import Decimal, getcontext, InvalidOperation # Para cálculos monetarios precisos

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy 

# --- CARGAR VARIABLES DE ENTORNO DESDE .env ---
# Esto debe hacerse muy temprano, idealmente antes de cualquier configuración que las use.
from dotenv import load_dotenv
load_dotenv() # Busca un archivo .env y carga sus variables en os.environ

# --- INICIALIZACIÓN DE LA APLICACIÓN FLASK ---
app = Flask(__name__)

# Configurar SECRET_KEY (leída desde .env o un valor default)
app.secret_key = os.environ.get('SECRET_KEY', 'CAMBIAR_ESTO_POR_UNA_CLAVE_SEGURA_EN_DESARROLLO_LOCAL')

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
DB_USERNAME = os.environ.get('DB_USERNAME_PA')
DB_PASSWORD = os.environ.get('DB_PASSWORD_PA')
DB_HOST = os.environ.get('DB_HOST_PA')
DB_NAME = os.environ.get('DB_NAME_PA')

if all([DB_USERNAME, DB_PASSWORD, DB_HOST, DB_NAME]):
    # Usar PyMySQL para la conexión
    app.config['SQLALCHEMY_DATABASE_URI'] = \
        f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}" # <--- CAMBIO AQUÍ
else:
    print("ADVERTENCIA: Variables de entorno para MySQL no configuradas. Usando SQLite local ('local_db.sqlite').")
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'local_db.sqlite')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) # Inicializa SQLAlchemy DESPUÉS de configurar la URI

# --- IMPORTAR MODELOS ---
# Es importante importar los modelos DESPUÉS de inicializar 'db',
# ya que los modelos dependen de 'db.Model'.
try:
    from models import User # Asume que models.py está al mismo nivel y define User
    MODELS_DISPONIBLES = True
except ImportError as e:
    MODELS_DISPONIBLES = False
    print(f"ADVERTENCIA: No se pudo importar el modelo User: {e}. Asegúrate de que models.py exista y esté correcto.")

# --- IMPORTAR Y REGISTRAR BLUEPRINTS ---
# Los Blueprints también se registran después de que 'app' (y 'db' si lo usan) estén listos.
try:
    from herramientas_bp.routes import herramientas_bp
    app.register_blueprint(herramientas_bp) # No se necesita url_prefix si la ruta ya es /herramientas/
    print("INFO: Blueprint 'herramientas_bp' registrado.")
except ImportError as e:
    print(f"Advertencia: No se pudo importar o registrar 'herramientas_bp': {e}. La ruta /herramientas no estará disponible.")

# Configuración de precisión para Decimal (opcional)
# getcontext().prec = 28 

# --- CLASE CombinacionSolver ---
class CombinacionSolver:
    # ... (tu clase CombinacionSolver sin cambios aquí, está bien como la tienes) ...
    # ... (Solo asegúrate de que los app.logger.info o app.logger.warning que tenías comentados
    # ... no se pueden usar directamente aquí a menos que pases 'app.logger' a la clase.
    # ... Los print() que tienes son una alternativa simple para la consola.)
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
                print(f"Advertencia en CombinacionSolver: Item inválido omitido: {data_row} debido a {e}")
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
        if self.time_limit_exceeded_flag:
            return

        if time.time() - self.start_time > self.time_limit_seconds:
            self.time_limit_exceeded_flag = True
            print(f"INFO en CombinacionSolver: Límite de tiempo de {self.time_limit_seconds}s alcanzado.")
            return

        if current_sum <= self.monto_objetivo and current_sum > self.best_sum_found:
            self.best_sum_found = current_sum
            self.best_selection_items_data = list(current_selection_data) 

        if index == self.num_items:
            return

        if current_sum + self.remaining_sum_array[index] < self.best_sum_found:
            return
        
        item_actual = self.items_procesados[index]
        if current_sum + item_actual['monto'] <= self.monto_objetivo: 
            current_selection_data.append(item_actual)
            self._solve_recursive(index + 1, current_sum + item_actual['monto'], current_selection_data)
            current_selection_data.pop() 

            if self.time_limit_exceeded_flag: 
                return

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
        print(f"INFO en CombinacionSolver: Búsqueda completada en {elapsed_time:.2f}s. Mejor suma: {self.best_sum_found}")
        if self.time_limit_exceeded_flag:
            print("ADVERTENCIA en CombinacionSolver: La búsqueda fue terminada por límite de tiempo. La solución podría no ser la óptima global.")
            
        return final_combination_output, self.best_sum_found, self.monto_objetivo, self.time_limit_exceeded_flag

# --- RUTAS PRINCIPALES DE LA APLICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def index():
    titulo_actual = "Comparador de Montos Excel" 
    
    if request.method == 'POST':
        if 'excel_file' in request.files:
            file = request.files['excel_file']
            if file.filename == '':
                return render_template('index.html', error_excel="No se seleccionó ningún archivo.", titulo_pagina=titulo_actual)
            if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
                try:
                    file_stream = io.BytesIO(file.read())
                    df = pd.read_excel(file_stream, engine='openpyxl')
                    file_stream.close() 
                    
                    column_id_name = None
                    column_monto_name = None
                    possible_id_cols = ['ID', 'Id', 'id', 'Comprobante', 'COMPROBANTE', 'Numero', 'Número']
                    possible_monto_cols = ['Monto', 'MONTO', 'Importe', 'IMPORTE', 'Valor', 'VALOR', 'Total', 'TOTAL']

                    for col_name_excel in df.columns:
                        if column_id_name is None and col_name_excel.strip().lower() in [p.lower() for p in possible_id_cols]:
                            column_id_name = col_name_excel
                        if column_monto_name is None and col_name_excel.strip().lower() in [p.lower() for p in possible_monto_cols]:
                            column_monto_name = col_name_excel
                        if column_id_name and column_monto_name: 
                            break
                    
                    if not column_id_name or not column_monto_name:
                        err_msg = "Columnas 'ID'/'Comprobante' y 'Monto'/'Importe' no encontradas. Verifique el Excel. Columnas encontradas: " + ", ".join(df.columns)
                        return render_template('index.html', error_excel=err_msg, titulo_pagina=titulo_actual)

                    excel_data_list = []
                    for _, row in df.iterrows():
                        try:
                            id_val = str(row[column_id_name])
                            monto_val = str(row[column_monto_name]) 
                            Decimal(monto_val) 
                            excel_data_list.append([id_val, monto_val])
                        except (InvalidOperation, KeyError, ValueError) as e_row :
                            app.logger.warning(f"Omitiendo fila por dato inválido: ID='{row.get(column_id_name)}', Monto='{row.get(column_monto_name)}'. Error: {e_row}")

                    if not excel_data_list:
                         return render_template('index.html', error_excel="No se encontraron datos válidos de ID y Monto en el Excel.", titulo_pagina=titulo_actual)

                    session['excel_data'] = excel_data_list
                    session['filename'] = file.filename
                    return redirect(url_for('index'))

                except Exception as e:
                    app.logger.error(f"Error leyendo el stream del archivo Excel: {e}", exc_info=True)
                    return render_template('index.html', error_excel=f"Error al leer el contenido del archivo Excel: {e}", titulo_pagina=titulo_actual)
            else:
                return render_template('index.html', error_excel="Formato de archivo no válido. Use .xlsx o .xls.", titulo_pagina=titulo_actual)

        elif 'monto_objetivo' in request.form and 'excel_data' in session:
            monto_objetivo_str = request.form['monto_objetivo']
            items_excel = session['excel_data'] 
            
            time_limit_config = 30 
            
            try:
                solver = CombinacionSolver(items_excel, monto_objetivo_str, time_limit_seconds=time_limit_config)
                combinacion, suma_obtenida, monto_objetivo_decimal, time_exceeded = solver.find_combination()
                
                suma_obtenida_str_disp = f"{suma_obtenida:.2f}"
                monto_objetivo_str_disp = f"{monto_objetivo_decimal:.2f}"
                combinacion_display = [(item_id, f"{monto_val:.2f}") for item_id, monto_val in combinacion]
                
                return render_template('results.html', 
                                       combinacion=combinacion_display, 
                                       suma_obtenida=suma_obtenida_str_disp, 
                                       monto_objetivo=monto_objetivo_str_disp,
                                       filename=session.get('filename'),
                                       time_exceeded=time_exceeded,
                                       time_limit_config=time_limit_config)
            except ValueError as e: 
                 app.logger.error(f"Error en solver: {e}", exc_info=True)
                 return render_template('index.html',
                                       excel_cargado=True,
                                       filename=session.get('filename'),
                                       error_monto=str(e), titulo_pagina=titulo_actual)
            except Exception as e_general:
                 app.logger.error(f"Error inesperado en búsqueda: {e_general}", exc_info=True)
                 return render_template('index.html',
                                       excel_cargado=True,
                                       filename=session.get('filename'),
                                       error_monto=f"Ocurrió un error inesperado: {e_general}", titulo_pagina=titulo_actual)
                                       
    excel_cargado = 'excel_data' in session
    filename = session.get('filename') if excel_cargado else None
    return render_template('index.html', excel_cargado=excel_cargado, filename=filename, titulo_pagina=titulo_actual)

@app.route('/reset')
def reset():
    session.pop('excel_data', None)
    session.pop('filename', None)
    return redirect(url_for('index'))

# --- COMANDO CLI PARA INICIALIZAR LA BASE DE DATOS ---
# Este comando es útil para crear las tablas en tu base de datos
# ejecutando "flask init-db" en la terminal.
@app.cli.command("init-db")
def init_db_command():
    """Crea las tablas de la base de datos."""
    if not MODELS_DISPONIBLES:
        print("Error: Modelos de base de datos no disponibles. No se pueden crear las tablas.")
        return
    try:
        db.create_all()
        print("Base de datos inicializada y tablas creadas (si no existían).")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
        print("Asegúrate de que las variables de entorno de la base de datos (DB_USERNAME_PA, etc.)")
        print("estén configuradas correctamente si esperas conectarte a MySQL.")

if __name__ == '__main__':
    import logging
    # Configuración básica de logging para desarrollo local
    logging.basicConfig(level=logging.INFO) 
    # app.logger.setLevel(logging.DEBUG) # Para más detalle si es necesario
    
    app.run(debug=True)