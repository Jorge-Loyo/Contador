from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import os
from decimal import Decimal, getcontext, InvalidOperation # Para cálculos monetarios precisos
import time # Para el límite de tiempo
import io # Para leer el archivo Excel en memoria
from flask_sqlalchemy import SQLAlchemy 

# --- 1. IMPORTAR EL BLUEPRINT ---
# Esta línea asume que tienes una carpeta llamada 'herramientas_bp' 
# y dentro de ella un archivo 'routes.py' donde defines 'herramientas_bp'.
# Si el archivo está en otro lugar o se llama diferente, ajusta la importación.
try:
    from herramientas_bp.routes import herramientas_bp
    BLUEPRINT_HERRAMIENTAS_DISPONIBLE = True
except ImportError:
    # Esto es útil si estás desarrollando y aún no has creado el blueprint.
    # La aplicación podrá seguir funcionando sin él (pero la ruta /herramientas no existirá).
    BLUEPRINT_HERRAMIENTAS_DISPONIBLE = False
    print("Advertencia: No se pudo importar 'herramientas_bp'. La ruta /herramientas no estará disponible.")


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'valor_default_para_desarrollo_local_12345!qlg_CAMBIAR_ESTO')

# --- 2. CONFIGURACIÓN DE UPLOAD_FOLDER (Opcional si todo es en memoria) ---
# Si realmente ya no guardas archivos en disco gracias a io.BytesIO, puedes comentar o eliminar estas líneas.
# Si alguna otra parte de tu app (o futuras herramientas) necesitan guardar archivos, mantenlo.
# UPLOAD_FOLDER = 'uploads' 
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# if not os.path.exists(UPLOAD_FOLDER) and UPLOAD_FOLDER == 'uploads': # Solo crear si es el default y no existe
#     os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
# Para producción en PythonAnywhere, es MEJOR usar variables de entorno para estos datos sensibles.
# Para desarrollo local, puedes ponerlos directamente, pero ¡NUNCA subas contraseñas a GitHub!

# Datos de tu base de datos MySQL en PythonAnywhere:
DB_USERNAME = os.environ.get('DB_USERNAME_PA') # En PA será 'Jloyo'
DB_PASSWORD = os.environ.get('DB_PASSWORD_PA') # La contraseña que estableciste para MySQL en PA
DB_HOST = os.environ.get('DB_HOST_PA')         # 'Jloyo.mysql.pythonanywhere-services.com'
DB_NAME = os.environ.get('DB_NAME_PA')         # 'Jloyo$default'

# Construir la URI de la base de datos
# Si alguna variable de entorno no está definida (ej. en local), podrías usar valores default o dar error
if all([DB_USERNAME, DB_PASSWORD, DB_HOST, DB_NAME]):
    app.config['SQLALCHEMY_DATABASE_URI'] = \
        f"mysql+mysqlclient://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
else:
    # Configuración para una base de datos SQLite local si las variables de entorno no están seteadas
    # Esto es útil para que puedas desarrollar localmente sin MySQL si lo prefieres.
    # SQLite guarda la base de datos en un archivo.
    print("ADVERTENCIA: Variables de entorno para MySQL no configuradas. Usando SQLite local ('local_db.sqlite').")
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'local_db.sqlite')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recomendado para desactivar notificaciones innecesarias

db = SQLAlchemy(app) # <--- INICIALIZA SQLAlchemy con tu app

# --- IMPORTAR MODELOS ---
# Esto es importante para que SQLAlchemy sepa de tus modelos
# y para que puedas usarlos en tus rutas.
# Asegúrate de que models.py esté al mismo nivel que app.py o ajusta la importación.
try:
    from models import User
except ImportError:
    print("ADVERTENCIA: No se pudo importar el modelo User. Asegúrate de que models.py exista y esté correcto.")
# --- FIN IMPORTAR MODELOS ---

# --- 3. REGISTRAR EL BLUEPRINT ---
if BLUEPRINT_HERRAMIENTAS_DISPONIBLE:
    app.register_blueprint(herramientas_bp)
    # No necesitas url_prefix aquí si la ruta principal del blueprint ya es '/herramientas/'
    # app.register_blueprint(herramientas_bp, url_prefix='/portal') # Ejemplo con prefijo

# Configurar precisión para Decimal (opcional, el default suele ser suficiente)
# getcontext().prec = 28 

class CombinacionSolver:
    # ... (tu clase CombinacionSolver sin cambios, está muy bien) ...
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
                # Usar app.logger si está disponible globalmente o pasar una instancia de logger
                # Por ahora, un print es seguro si app.logger no está definido en este scope.
                print(f"Advertencia: Item inválido omitido: {data_row} debido a {e}")
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
            # app.logger.info(f"Límite de tiempo de {self.time_limit_seconds}s alcanzado.") # Idem logger
            print(f"INFO: Límite de tiempo de {self.time_limit_seconds}s alcanzado.")
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
        # app.logger.info(f"Búsqueda completada en {elapsed_time:.2f}s. Mejor suma: {self.best_sum_found}") # Idem logger
        print(f"INFO: Búsqueda completada en {elapsed_time:.2f}s. Mejor suma: {self.best_sum_found}")
        if self.time_limit_exceeded_flag:
            # app.logger.warning("Advertencia: La búsqueda fue terminada por límite de tiempo...") # Idem logger
            print("ADVERTENCIA: La búsqueda fue terminada por límite de tiempo. La solución podría no ser la óptima global.")
            
        return final_combination_output, self.best_sum_found, self.monto_objetivo, self.time_limit_exceeded_flag


@app.route('/', methods=['GET', 'POST'])
def index():
    # --- 4. AÑADIR título_pagina AL CONTEXTO DE LA PLANTILLA ---
    # Esto es opcional, pero ayuda a mantener la consistencia si tus plantillas esperan esta variable.
    # Lo habías mencionado en la guía anterior.
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
    # La limpieza de la carpeta 'uploads' ya no es necesaria si todo es en memoria
    return redirect(url_for('index'))

if __name__ == '__main__':
    import logging
    # --- 5. CONFIGURACIÓN DE LOGGING MEJORADA ---
    # Es bueno configurar esto para que app.logger funcione correctamente durante el desarrollo local.
    # PythonAnywhere tiene su propio sistema de logging para producción.
    if not app.debug: # No configurar logging si Flask está en modo debug, ya que lo maneja diferente
        # Para desarrollo local, si no está en modo debug (ej. app.run(debug=False))
        # o si quieres forzarlo.
        pass # Puedes añadir handlers específicos si es necesario.
    
    # Si quieres que app.logger.warning y app.logger.error siempre se muestren en consola local:
    logging.basicConfig(level=logging.INFO) # Muestra INFO, WARNING, ERROR, CRITICAL
    # Si tu CombinacionSolver usa app.logger y quieres ver esos mensajes,
    # tendrías que pasar la instancia de app.logger a la clase o hacerla accesible globalmente
    # (lo cual no es ideal). Por ahora, los prints dentro de la clase son una solución simple.

    app.run(debug=True)