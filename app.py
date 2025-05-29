from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
# itertools.combinations ya no será el método principal para esto, pero puede quedar
# import numpy as np # Ya no es estrictamente necesario para la nueva solución principal
import os
from decimal import Decimal, getcontext, InvalidOperation # Para cálculos monetarios precisos
import time # Para el límite de tiempo
import io # Añade esta importación al principio de app.py

app = Flask(__name__)
app.secret_key = 'tu_super_secreta_llave_MUY_SECRETA' # Cambia esto en producción
UPLOAD_FOLDER = 'uploads' # Carpeta para archivos subidos
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegurarse de que la carpeta 'uploads' exista
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configurar precisión para Decimal (opcional, el default suele ser suficiente)
# getcontext().prec = 28 

class CombinacionSolver:
    def __init__(self, items_original_lista, monto_objetivo_str, time_limit_seconds=30):
        self.items_procesados = []
        try:
            self.monto_objetivo = Decimal(monto_objetivo_str)
        except InvalidOperation:
            raise ValueError("El monto objetivo ingresado no es un número válido.")

        self.time_limit_seconds = time_limit_seconds
        self.start_time = 0
        self.time_limit_exceeded_flag = False # Usamos un flag simple

        self.best_sum_found = Decimal('0')
        # Almacenará los ítems (diccionarios) de la mejor combinación
        self.best_selection_items_data = [] 

        if self.monto_objetivo <= 0:
            # No tiene sentido buscar para montos no positivos
            return

        # Preprocesar y filtrar ítems
        for idx, data_row in enumerate(items_original_lista): # data_row es [id_val, monto_val]
            try:
                item_id = data_row[0]
                monto_val_str = str(data_row[1]) # Asegurar que sea string antes de Decimal
                monto = Decimal(monto_val_str)

                if monto <= Decimal('0'): # Ignorar montos no positivos
                    continue
                # Si un solo item ya excede el monto objetivo y buscamos sumas <= objetivo,
                # podría filtrarse aquí, pero la lógica de recursión lo manejará.
                # Sin embargo, para la heurística de ordenamiento, es mejor mantenerlos si son positivos.
                
                self.items_procesados.append({
                    'id': item_id,
                    'monto': monto,
                    # Podrías añadir 'original_index': idx si lo necesitas para algo más
                })
            except Exception as e:
                app.logger.warning(f"Item inválido omitido: {data_row} debido a {e}")
                continue
        
        # Ordenar ítems por monto en orden descendente.
        # Ayuda a encontrar soluciones altas más rápido y a podar más eficientemente.
        self.items_procesados.sort(key=lambda x: x['monto'], reverse=True)
        
        self.num_items = len(self.items_procesados)
        
        # Precalcular la suma de los montos restantes para una poda más eficiente
        self.remaining_sum_array = [Decimal('0')] * (self.num_items + 1)
        if self.num_items > 0:
            current_remaining_sum = Decimal('0')
            for i in range(self.num_items - 1, -1, -1):
                current_remaining_sum += self.items_procesados[i]['monto']
                self.remaining_sum_array[i] = current_remaining_sum
        
    def _solve_recursive(self, index, current_sum, current_selection_data):
        if self.time_limit_exceeded_flag:
            return

        # Chequeo de límite de tiempo
        if time.time() - self.start_time > self.time_limit_seconds:
            self.time_limit_exceeded_flag = True
            app.logger.info(f"Límite de tiempo de {self.time_limit_seconds}s alcanzado.")
            return

        # Poda 1: Si la suma actual ya excede el objetivo (no debería pasar si se añade correctamente)
        # Esta condición es más bien una guarda por si se añade un item que lo excede.
        # La lógica principal de no añadir si excede está antes de la llamada recursiva.

        # Actualizar la mejor solución encontrada
        # Solo consideramos sumas <= monto_objetivo
        if current_sum <= self.monto_objetivo and current_sum > self.best_sum_found:
            self.best_sum_found = current_sum
            self.best_selection_items_data = list(current_selection_data) # Copia de la selección actual
            # Si encontramos el objetivo exacto, podríamos parar si esa es la meta principal.
            # Pero para "lo más cerca por debajo", seguimos buscando por si hay otra combinación igual.
            # if current_sum == self.monto_objetivo:
            # self.time_limit_exceeded_flag = True # Opcional: parar si se alcanza el exacto
            # return


        # Caso base: Todos los ítems han sido considerados
        if index == self.num_items:
            return

        # Poda 2: Si la suma actual + toda la suma restante posible no puede superar la mejor ya encontrada
        if current_sum + self.remaining_sum_array[index] < self.best_sum_found:
            return
        
        # --- Opción 1: Incluir el ítem actual (items_procesados[index]) ---
        item_actual = self.items_procesados[index]
        if current_sum + item_actual['monto'] <= self.monto_objetivo: # Solo incluir si no excede el objetivo
            current_selection_data.append(item_actual)
            self._solve_recursive(index + 1, current_sum + item_actual['monto'], current_selection_data)
            current_selection_data.pop() # Backtrack: remover el ítem para explorar la otra rama

            if self.time_limit_exceeded_flag: # Chequear después de la llamada recursiva
                return

        # --- Opción 2: Excluir el ítem actual (items_procesados[index]) ---
        # No es necesario añadir ninguna poda específica aquí antes de la llamada,
        # la poda general (Poda 2) al inicio de la función se encargará.
        self._solve_recursive(index + 1, current_sum, current_selection_data)

    def find_combination(self):
        if self.monto_objetivo <= 0 or not self.items_procesados:
            return [], Decimal('0'), self.monto_objetivo, self.time_limit_exceeded_flag

        self.start_time = time.time()
        self.time_limit_exceeded_flag = False # Resetear flag
        self.best_sum_found = Decimal('0')
        self.best_selection_items_data = []

        self._solve_recursive(0, Decimal('0'), [])
        
        # Preparar la salida final con (id, monto)
        final_combination_output = []
        for item_data in self.best_selection_items_data:
            final_combination_output.append((item_data['id'], item_data['monto']))
            
        elapsed_time = time.time() - self.start_time
        app.logger.info(f"Búsqueda completada en {elapsed_time:.2f}s. Mejor suma: {self.best_sum_found}")
        if self.time_limit_exceeded_flag:
            app.logger.warning("Advertencia: La búsqueda fue terminada por límite de tiempo. La solución podría no ser la óptima global.")
            
        return final_combination_output, self.best_sum_found, self.monto_objetivo, self.time_limit_exceeded_flag


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'excel_file' in request.files:
            file = request.files['excel_file']
            if file.filename == '':
                return render_template('index.html', error_excel="No se seleccionó ningún archivo.")
            if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
                try:
                    #filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                    #file.save(filepath)
                    #df = pd.read_excel(filepath, engine='openpyxl') # Especificar engine
                    # Leer el contenido del archivo en un stream de bytes en memoria
                    file_stream = io.BytesIO(file.read())
                    df = pd.read_excel(file_stream, engine='openpyxl')
                    file_stream.close() # Buena práctica cerrar el stream
                    
                    # Detección más robusta de columnas
                    column_id_name = None
                    column_monto_name = None
                    possible_id_cols = ['ID', 'Id', 'id', 'Comprobante', 'COMPROBANTE', 'Numero', 'Número']
                    possible_monto_cols = ['Monto', 'MONTO', 'Importe', 'IMPORTE', 'Valor', 'VALOR', 'Total', 'TOTAL']

                    for col_name_excel in df.columns:
                        if column_id_name is None and col_name_excel.strip().lower() in [p.lower() for p in possible_id_cols]:
                            column_id_name = col_name_excel
                        if column_monto_name is None and col_name_excel.strip().lower() in [p.lower() for p in possible_monto_cols]:
                            column_monto_name = col_name_excel
                        if column_id_name and column_monto_name: # Optimización: si ya encontraste ambas
                            break
                    
                    if not column_id_name or not column_monto_name:
                        err_msg = "Columnas 'ID'/'Comprobante' y 'Monto'/'Importe' no encontradas. Verifique el Excel. Columnas encontradas: " + ", ".join(df.columns)
                        return render_template('index.html', error_excel=err_msg)

                    # Limpiar y convertir montos
                    # No convertir a float aquí, mantener como string o pd.Series[object] para Decimal
                    # df[column_monto_name] = pd.to_numeric(df[column_monto_name], errors='coerce')
                    # df.dropna(subset=[column_monto_name], inplace=True)
                    
                    # Guardar datos en la sesión (lista de listas)
                    # Asegúrate que los montos se guardan como string para preservar precisión para Decimal
                    excel_data_list = []
                    for _, row in df.iterrows():
                        try:
                            id_val = str(row[column_id_name])
                            monto_val = str(row[column_monto_name]) # Guardar como string
                            # Validar que el monto pueda ser un Decimal antes de añadir
                            Decimal(monto_val) # Intenta convertir, si falla, omite la fila
                            excel_data_list.append([id_val, monto_val])
                        except (InvalidOperation, KeyError, ValueError) as e_row :
                            app.logger.warning(f"Omitiendo fila por dato inválido: ID='{row.get(column_id_name)}', Monto='{row.get(column_monto_name)}'. Error: {e_row}")


                    if not excel_data_list:
                         return render_template('index.html', error_excel="No se encontraron datos válidos de ID y Monto en el Excel.")

                    session['excel_data'] = excel_data_list
                    session['filename'] = file.filename
                    return redirect(url_for('index'))

                except Exception as e:
                    app.logger.error(f"Error leyendo el stream del archivo Excel: {e}", exc_info=True)
                    return render_template('index.html', error_excel=f"Error al leer el contenido del archivo Excel: {e}")
            else:
                return render_template('index.html', error_excel="Formato de archivo no válido. Use .xlsx o .xls.")

        elif 'monto_objetivo' in request.form and 'excel_data' in session:
            monto_objetivo_str = request.form['monto_objetivo']
            items_excel = session['excel_data'] # Lista de [id_str, monto_str]
            
            time_limit_config = 30 # segundos, puedes ajustarlo o hacerlo configurable
            
            try:
                solver = CombinacionSolver(items_excel, monto_objetivo_str, time_limit_seconds=time_limit_config)
                combinacion, suma_obtenida, monto_objetivo_decimal, time_exceeded = solver.find_combination()
                
                # Formatear para la plantilla
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
            except ValueError as e: # Error de conversión de monto_objetivo o similar
                 app.logger.error(f"Error en solver: {e}", exc_info=True)
                 return render_template('index.html',
                                   excel_cargado=True,
                                   filename=session.get('filename'),
                                   error_monto=str(e))
            except Exception as e_general:
                 app.logger.error(f"Error inesperado en búsqueda: {e_general}", exc_info=True)
                 return render_template('index.html',
                                   excel_cargado=True,
                                   filename=session.get('filename'),
                                   error_monto=f"Ocurrió un error inesperado: {e_general}")
                                   
    excel_cargado = 'excel_data' in session
    filename = session.get('filename') if excel_cargado else None
    return render_template('index.html', excel_cargado=excel_cargado, filename=filename)

@app.route('/reset')
def reset():
    session.pop('excel_data', None)
    session.pop('filename', None)
    # Considera si quieres borrar los archivos de la carpeta 'uploads' también
    # for f_name in os.listdir(app.config['UPLOAD_FOLDER']):
    #     try:
    #         os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f_name))
    #     except Exception as e_rem:
    #         app.logger.error(f"No se pudo borrar el archivo {f_name}: {e_rem}")
    return redirect(url_for('index'))

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO) # Configura el logging básico para ver los logs de app
    # Para debug más detallado durante el desarrollo:
    # logging.getLogger('werkzeug').setLevel(logging.INFO) 
    # app.logger.setLevel(logging.DEBUG)
    app.run(debug=True)