import os
import io
import base64
import hashlib
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, Response, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import date, timedelta, datetime
import json
from functools import wraps # Importar wraps para los decoradores
import re # Importar re para validación de email

# Inicialización de la aplicación Flask
app = Flask(__name__)
# Configura una clave secreta para la gestión de sesiones.
# ¡IMPORTANTE! En un entorno de producción, usa una clave secreta fuerte y generada aleatoriamente.
app.secret_key = 'your_super_secret_key_here' # Cambia esto por una clave segura

# 🔌 Configuración de la Conexión a MySQL
# Esta función establece y devuelve una conexión a la base de datos SofiaComics.
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='1234', # Asegúrate de que esta sea tu contraseña de MySQL
            database='SofiaComics'
        )
        return conn
    except Error as e:
        print(f"Error al conectar a MySQL: {e}")
        return None

# --- Funciones de Utilidad ---

# Función para hashear contraseñas usando SHA256
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Función para verificar contraseñas hasheadas
def check_password(hashed_password, password):
    return hashed_password == hashlib.sha256(password.encode()).hexdigest()

# Decorador para requerir que el usuario esté logueado
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session.get('logged_in'):
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para requerir que el usuario sea editorial
def editorial_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_type' not in session or session.get('user_type') != 'editorial':
            flash('Acceso denegado. Solo editoriales pueden acceder a esta página.', 'danger')
            return redirect(url_for('home')) # O a la página de login
        return f(*args, **kwargs)
    return decorated_function

# Decorador para requerir que el usuario sea maestro (admin)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Asumimos que el usuario maestro tiene un correo_usuario específico
        # Por ejemplo, 'admin@sofiacomics.com'
        if 'user_type' not in session or session.get('user_type') != 'admin':
            flash('Acceso denegado. Solo el usuario maestro puede acceder a esta página.', 'danger')
            return redirect(url_for('home')) # O a la página de login
        return f(*args, **kwargs)
    return decorated_function

# Helper para obtener el ID de una editorial de forma flexible (insensible a mayúsculas/minúsculas y con nombres alternativos)
def get_editorial_id_flexible(editorial_names_list):
    conn = get_db_connection()
    editorial_id = None
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Convertir todos los nombres a minúsculas para la búsqueda case-insensitive
            lower_names = [name.lower() for name in editorial_names_list]
            placeholders = ', '.join(['%s'] * len(lower_names))
            query = f"SELECT id_editorial FROM Editorial WHERE LOWER(nombre) IN ({placeholders})"
            cursor.execute(query, tuple(lower_names))
            result = cursor.fetchone()
            if result:
                editorial_id = result['id_editorial']
            else:
                print(f"Advertencia: No se encontró la editorial con los nombres (flexibles) '{editorial_names_list}' en la base de datos.")
        except Error as e:
            print(f"Error al obtener ID de editorial para {editorial_names_list}: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return editorial_id

# --- Rutas de Autenticación ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            user = None

            # Intentar buscar en la tabla Usuario
            cursor.execute("SELECT * FROM Usuario WHERE correo_usuario = %s", (email,))
            user = cursor.fetchone()

            if user and check_password(user['contraseña'], password):
                # Es un usuario normal
                session['logged_in'] = True
                session['user_email'] = user['correo_usuario']
                session['user_name'] = user['nombre']
                session['user_type'] = 'user'
                flash('Has iniciado sesión correctamente.', 'success')
                return redirect(url_for('home'))
            else:
                # Si no es un usuario normal, intentar buscar en la tabla Usuario_editorial
                cursor.execute("SELECT ue.*, e.nombre AS editorial_nombre FROM Usuario_editorial ue JOIN Editorial e ON ue.id_editorial = e.id_editorial WHERE ue.correo_editorial = %s", (email,))
                editorial_user = cursor.fetchone()

                if editorial_user and check_password(editorial_user['contraseña'], password):
                    # Es un usuario editorial
                    session['logged_in'] = True
                    session['user_email'] = editorial_user['correo_editorial']
                    session['user_name'] = editorial_user['nombre']
                    session['user_type'] = 'editorial'
                    session['editorial_id'] = editorial_user['id_editorial']
                    session['editorial_name'] = editorial_user['editorial_nombre']

                    # Redirigir al usuario editorial a su página de tickets específica
                    editorial_name_lower = editorial_user['editorial_nombre'].lower()
                    if editorial_name_lower in ['marvel comics', 'marvel']:
                        flash(f'Has iniciado sesión como editorial: {editorial_user["editorial_nombre"]}.', 'success')
                        return redirect(url_for('editorial_upload_marvel'))
                    elif editorial_name_lower == 'dc comics':
                        flash(f'Has iniciado sesión como editorial: {editorial_user["editorial_nombre"]}.', 'success')
                        return redirect(url_for('editorial_upload_dc'))
                    elif editorial_name_lower == 'indie comics':
                        flash(f'Has iniciado sesión como editorial: {editorial_user["editorial_nombre"]}.', 'success')
                        return redirect(url_for('editorial_upload_indie'))
                    else:
                        # Fallback si la editorial no tiene una página de tickets específica configurada
                        flash(f'Has iniciado sesión como editorial: {editorial_user["editorial_nombre"]}. No hay una página de subida específica para tu editorial.', 'warning')
                        return redirect(url_for('editorial_dashboard'))
                else:
                    # Finalmente, verificar si es el usuario maestro (admin)
                    # Asumimos un correo y contraseña fijos para el admin por simplicidad,
                    # en un entorno real, esto se gestionaría de forma más robusta.
                    if email == 'admin@sofiacomics.com' and password == 'admin123': # ¡CAMBIA ESTO!
                        session['logged_in'] = True
                        session['user_email'] = email
                        session['user_name'] = 'Usuario Maestro'
                        session['user_type'] = 'admin'
                        flash('Has iniciado sesión como Usuario Maestro.', 'success')
                        return redirect(url_for('admin_dashboard'))
                    else:
                        flash('Correo o contraseña incorrectos.', 'danger')
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return render_template('Login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    characters = []
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Obtener todos los personajes de la base de datos
            cursor.execute("SELECT id_personaje, nombre, imagen FROM Personaje ORDER BY nombre ASC")
            characters_data = cursor.fetchall()
            for char in characters_data:
                if char['imagen']:
                    # Convertir BLOB a base64 para incrustar en HTML
                    char['imagen_b64'] = base64.b64encode(char['imagen']).decode('utf-8')
                else:
                    char['imagen_b64'] = None # O una imagen de placeholder
                characters.append(char)
        except Error as e:
            flash(f"Error al cargar personajes: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        selected_characters_json = request.form.get('selected_characters')

        # Validaciones básicas en el backend (además de las de JS)
        if not name or not email or not password or not confirm_password:
            flash('Todos los campos obligatorios deben ser llenados.', 'danger')
            return render_template('CreacionDeCuenta.html', characters=characters)
        if password != confirm_password:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('CreacionDeCuenta.html', characters=characters)
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return render_template('CreacionDeCuenta.html', characters=characters)

        hashed_password = hash_password(password)
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                # Insertar usuario
                cursor.execute(
                    "INSERT INTO Usuario (correo_usuario, nombre, contraseña, fecha_creacion) VALUES (%s, %s, %s, CURDATE())",
                    (email, name, hashed_password)
                )
                conn.commit()

                # Insertar preferencias de usuario
                if selected_characters_json:
                    selected_character_ids = json.loads(selected_characters_json)
                    if 0 < len(selected_character_ids) <= 3: # Validar también en el backend
                        for personaje_id in selected_character_ids:
                            cursor.execute(
                                "INSERT INTO Preferencias_usuario (correo_usuario, id_personaje, fecha_agregado) VALUES (%s, %s, CURDATE())",
                                (email, int(personaje_id))
                            )
                        conn.commit()
                    else:
                        flash('Error: Debes seleccionar entre 1 y 3 personajes favoritos.', 'danger')
                        conn.rollback() # Deshacer la creación del usuario si las preferencias son inválidas
                        return render_template('CreacionDeCuenta.html', characters=characters)

                flash('Cuenta creada exitosamente. ¡Ahora puedes iniciar sesión!', 'success')
                return redirect(url_for('login'))
            except Error as e:
                if e.errno == 1062: # Código de error para entrada duplicada (Duplicate entry for primary key)
                    flash('Ese correo electrónico ya está registrado.', 'danger')
                else:
                    flash(f'Error al registrar la cuenta: {e}', 'danger')
                conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
    return render_template('CreacionDeCuenta.html', characters=characters) # Pasar personajes al template

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('home'))

# --- Rutas Principales ---

@app.route('/')
def home():
    conn = get_db_connection()
    most_read_comics_month = []
    favorite_character_comics = []

    current_month_name = datetime.now().strftime('%B').capitalize() # Nombre del mes actual en español
    current_year = datetime.now().year

    # Diccionario para traducir el nombre del mes a español
    month_names_es = {
        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril',
        'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto',
        'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
    }
    current_month_name = month_names_es.get(datetime.now().strftime('%B'), datetime.now().strftime('%B')).capitalize()


    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Lógica para cómics más leídos del mes
            # Consulta para obtener los cómics más leídos del mes (ejemplo: los 15 más recientes)
            # Se incluye c.fecha_publicacion en SELECT y GROUP BY para compatibilidad con ONLY_FULL_GROUP_BY
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.portada, c.fecha_publicacion, COUNT(hl.codigo_de_barras) AS read_count
                FROM Comic c
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE MONTH(c.fecha_publicacion) = %s AND YEAR(c.fecha_publicacion) = %s
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.portada, c.fecha_publicacion
                ORDER BY read_count DESC, c.fecha_publicacion DESC
                LIMIT 15
            """, (datetime.now().month, current_year))
            comics_data = cursor.fetchall()

            # Convertir BLOB de portada a base64 para cada cómic
            for comic in comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                most_read_comics_month.append(comic)

            # Lógica para cómics de personajes favoritos (si el usuario está logueado)
            if 'logged_in' in session and session['user_type'] == 'user':
                user_email = session['user_email']
                # Obtener los personajes favoritos del usuario
                cursor.execute("""
                    SELECT id_personaje FROM Preferencias_usuario WHERE correo_usuario = %s
                """, (user_email,))
                favorite_character_ids = [row['id_personaje'] for row in cursor.fetchall()]

                if favorite_character_ids:
                    # Obtener cómics relacionados con esos personajes
                    # Se incluye c.fecha_publicacion en SELECT DISTINCT para compatibilidad con ONLY_FULL_GROUP_BY
                    placeholders = ','.join(['%s'] * len(favorite_character_ids))
                    query = f"""
                        SELECT DISTINCT c.codigo_de_barras, c.titulo, c.autor, c.portada, c.fecha_publicacion
                        FROM Comic c
                        JOIN ComicPersonaje cp ON c.codigo_de_barras = cp.codigo_de_barras
                        WHERE cp.id_personaje IN ({placeholders})
                        ORDER BY c.fecha_publicacion DESC
                        LIMIT 10
                    """
                    cursor.execute(query, tuple(favorite_character_ids))
                    fav_comics_raw = cursor.fetchall()

                    for comic in fav_comics_raw:
                        if comic['portada']:
                            comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                        else:
                            comic['portada_b64'] = None
                        favorite_character_comics.append(comic)
                else:
                    flash('No has seleccionado personajes favoritos. Visita tu perfil para hacerlo.', 'info')

        except Error as e:
            flash(f"Error al cargar cómics: {e}", 'danger')
            print(f"Error al cargar cómics: {e}") # Para depuración en consola
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('index.html',
                           most_read_comics_month=most_read_comics_month,
                           current_month_name=current_month_name,
                           favorite_character_comics=favorite_character_comics)

# --- Nueva Ruta para Sugerencias de Búsqueda (AJAX) ---
@app.route('/search_suggestions')
def search_suggestions():
    query = request.args.get('query', '').strip()
    suggestions = []
    if query:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            try:
                search_pattern = f"%{query}%"
                cursor.execute("""
                    SELECT codigo_de_barras, titulo
                    FROM Comic
                    WHERE titulo LIKE %s
                    ORDER BY titulo ASC
                    LIMIT 10
                """, (search_pattern,))
                suggestions = cursor.fetchall()
            except Error as e:
                print(f"Error al obtener sugerencias de búsqueda: {e}")
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
    return jsonify(suggestions)


# --- Rutas de Cómics por Editorial (Públicas) ---

@app.route('/marvel_comics')
def marvel_comics():
    conn = get_db_connection()
    comics = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Buscar cómics asociados a 'Marvel Comics' o 'Marvel'
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, e.nombre AS editorial_nombre
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                WHERE LOWER(e.nombre) IN ('marvel comics', 'marvel')
                ORDER BY c.titulo
            """)
            comics_data = cursor.fetchall()
            for comic in comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                comics.append(comic)
        except Error as e:
            flash(f"Error al cargar cómics de Marvel: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return render_template('MarvelComics.html', comics=comics)

@app.route('/dc_comics')
def dc_comics():
    conn = get_db_connection()
    comics = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, e.nombre AS editorial_nombre
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                WHERE LOWER(e.nombre) = 'dc comics'
                ORDER BY c.titulo
            """)
            comics_data = cursor.fetchall()
            for comic in comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                comics.append(comic)
        except Error as e:
            flash(f"Error al cargar cómics de DC: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return render_template('DCComics.html', comics=comics)

@app.route('/indie_comics')
def indie_comics():
    conn = get_db_connection()
    comics = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Excluir explícitamente Marvel y DC, incluyendo sus posibles variaciones
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, e.nombre AS editorial_nombre
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                WHERE LOWER(e.nombre) NOT IN ('marvel comics', 'marvel', 'dc comics')
                ORDER BY c.titulo
            """)
            comics_data = cursor.fetchall()
            for comic in comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                comics.append(comic)
        except Error as e:
            flash(f"Error al cargar cómics Indie: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return render_template('IndieComics.html', comics=comics)

# --- Rutas de Detalle y Lectura de Cómic ---

@app.route('/comic/<int:comic_id>', methods=['GET', 'POST'])
def comic_detail(comic_id):
    comic = None
    average_rating = None
    user_rating = None
    characters = [] # Inicializa la lista de personajes

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Obtener detalles del cómic
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.fecha_publicacion, c.portada, e.nombre AS editorial_nombre
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                WHERE c.codigo_de_barras = %s
            """, (comic_id,))
            comic = cursor.fetchone()

            if comic:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None

                # Obtener calificación promedio
                cursor.execute("SELECT AVG(calificacion) AS avg_rating FROM Calificaciones WHERE codigo_de_barras = %s", (comic_id,))
                avg_result = cursor.fetchone()
                if avg_result and avg_result['avg_rating'] is not None:
                    average_rating = round(avg_result['avg_rating'], 2)

                # Si el usuario está logueado, obtener su calificación
                if 'logged_in' in session and session['user_type'] == 'user':
                    user_email = session['user_email']
                    cursor.execute("SELECT calificacion FROM Calificaciones WHERE correo_usuario = %s AND codigo_de_barras = %s", (user_email, comic_id))
                    user_rating_result = cursor.fetchone()
                    if user_rating_result:
                        user_rating = user_rating_result['calificacion']

                # Procesar envío de calificación (si es POST y el usuario está logueado)
                if request.method == 'POST' and 'logged_in' in session and session['user_type'] == 'user':
                    rating = request.form.get('rating')
                    if rating and rating.isdigit() and 1 <= int(rating) <= 5:
                        user_email = session['user_email']
                        try:
                            # Insertar o actualizar la calificación del usuario
                            cursor.execute("""
                                INSERT INTO Calificaciones (correo_usuario, codigo_de_barras, calificacion)
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE calificacion = %s
                            """, (user_email, comic_id, int(rating), int(rating)))
                            conn.commit()
                            flash('Tu calificación ha sido guardada.', 'success')
                            # Recalcular el promedio y la calificación del usuario para la vista actualizada
                            cursor.execute("SELECT AVG(calificacion) AS avg_rating FROM Calificaciones WHERE codigo_de_barras = %s", (comic_id,))
                            avg_result = cursor.fetchone()
                            if avg_result and avg_result['avg_rating'] is not None:
                                average_rating = round(avg_result['avg_rating'], 2)
                            user_rating = int(rating) # Actualizar la calificación del usuario en la sesión actual
                        except Error as e:
                            flash(f'Error al guardar tu calificación: {e}', 'danger')
                            conn.rollback()
                    else:
                        flash('Por favor, selecciona una calificación válida (1-5).', 'danger')
                
                # --- NUEVO: Obtener personajes asociados al cómic ---
                cursor.execute("""
                    SELECT p.id_personaje, p.nombre, p.descripcion, p.imagen, e.nombre AS editorial_nombre
                    FROM Personaje p
                    JOIN ComicPersonaje cp ON p.id_personaje = cp.id_personaje
                    LEFT JOIN Editorial e ON p.id_editorial = e.id_editorial
                    WHERE cp.codigo_de_barras = %s
                    ORDER BY p.nombre ASC
                """, (comic_id,))
                characters_data = cursor.fetchall()
                for char in characters_data:
                    if char['imagen']:
                        char['imagen_b64'] = base64.b64encode(char['imagen']).decode('utf-8')
                    else:
                        char['imagen_b64'] = None
                    characters.append(char)

        except Error as e:
            flash(f"Error al cargar detalles del cómic o procesar calificación: {e}", 'danger')
            print(f"Error en comic_detail: {e}") # Para depuración
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if not comic:
        flash('Cómic no encontrado.', 'danger')
        return redirect(url_for('home')) # Redirigir a la página principal si el cómic no existe

    return render_template('precomic.html', comic=comic, average_rating=average_rating, user_rating=user_rating, characters=characters)


@app.route('/read_comic/<int:comic_id>')
@login_required # Solo usuarios logueados pueden leer cómics
def read_comic(comic_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Permitir que el usuario admin lea cómics sin suscripción
            if session.get('user_type') == 'admin':
                print("Admin user detected, bypassing subscription check.")
                pass # El admin puede leer sin suscripción
            else:
                # Verificar si el usuario tiene una suscripción activa
                user_email = session['user_email']
                cursor.execute("""
                    SELECT s.estado FROM Suscripciones s
                    WHERE s.correo_usuario = %s AND s.id_plan IN (1, 2, 3) AND estado = 'Activa' AND fecha_fin >= CURDATE()
                """, (user_email,))
                subscription = cursor.fetchone()

                if not subscription:
                    flash('Necesitas una suscripción activa para leer cómics. ¡Suscríbete ahora!', 'warning')
                    return redirect(url_for('subscriptions'))

            # Obtener el contenido BLOB del cómic
            cursor.execute("SELECT contenido FROM Comic WHERE codigo_de_barras = %s", (comic_id,))
            comic_data = cursor.fetchone()

            if comic_data and comic_data['contenido']:
                # Registrar en el historial de lectura
                try:
                    # Solo registrar si no es admin, o si se desea registrar también las lecturas del admin
                    if session.get('user_type') != 'admin':
                        cursor.execute(
                            "INSERT INTO HistorialLectura (correo_usuario, codigo_de_barras, fecha_lectura) VALUES (%s, %s, CURRENT_TIMESTAMP)",
                            (session['user_email'], comic_id)
                        )
                        conn.commit()
                except Error as e:
                    # Si ya existe una entrada reciente, simplemente ignorar o actualizar timestamp
                    print(f"Error al registrar historial de lectura (puede ser duplicado): {e}")
                    conn.rollback() # Deshacer si hubo un error en el insert

                # Servir el contenido como PDF
                # Asegúrate de que el contenido BLOB es un PDF válido
                return Response(comic_data['contenido'], mimetype='application/pdf')
            else:
                flash('Contenido del cómic no disponible.', 'danger')
                return redirect(url_for('comic_detail', comic_id=comic_id))
        except Error as e:
            flash(f"Error al cargar el cómic: {e}", 'danger')
            return redirect(url_for('comic_detail', comic_id=comic_id))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return redirect(url_for('home'))

# --- Rutas de Suscripción y Pago ---

@app.route('/subscriptions')
def subscriptions():
    conn = get_db_connection()
    plans = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM Planes_suscripcion ORDER BY costo_suscripcion ASC")
            plans = cursor.fetchall()
        except Error as e:
            flash(f"Error al cargar planes de suscripción: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return render_template('Suscripcion.html', plans=plans)

@app.route('/checkout/<int:plan_id>', methods=['GET', 'POST'])
@login_required # Solo usuarios logueados pueden realizar transacciones
def checkout(plan_id):
    conn = get_db_connection()
    plan = None
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM Planes_suscripcion WHERE id_plan = %s", (plan_id,))
            plan = cursor.fetchone()
        except Error as e:
            flash(f"Error al cargar detalles del plan: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if not plan:
        flash('Plan de suscripción no encontrado.', 'danger')
        return redirect(url_for('subscriptions'))

    if request.method == 'POST':
        # Aquí iría la lógica de procesamiento de pago real (pasarela de pago)
        # Por simplicidad, simularemos una transacción exitosa.
        user_email = session['user_email']
        payment_method = request.form.get('payment_method', 'Tarjeta de Crédito') # Ejemplo
        reference = f"TRANS_{plan_id}_{user_email}_{os.urandom(4).hex()}" # Referencia única

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                # Insertar transacción
                cursor.execute(
                    "INSERT INTO Transacciones (correo_usuario, id_plan, cantidad, fecha_transaccion, metodo_pago, referencia, estado) VALUES (%s, %s, %s, CURDATE(), %s, %s, %s)",
                    (user_email, plan['id_plan'], plan['costo_suscripcion'], payment_method, reference, 'Completada')
                )
                # Insertar o actualizar suscripción
                # Calcular fecha de fin
                start_date = date.today()
                end_date = start_date + timedelta(days=plan['duracion_meses'] * 30) # Aproximado
                cursor.execute("""
                    INSERT INTO Suscripciones (correo_usuario, id_plan, fecha_inicio, fecha_fin, estado)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE id_plan = %s, fecha_inicio = %s, fecha_fin = %s, estado = %s
                """, (user_email, plan['id_plan'], start_date, end_date, 'Activa',
                      plan['id_plan'], start_date, end_date, 'Activa'))
                conn.commit()
                flash('Pago y suscripción procesados exitosamente. ¡Disfruta de tus cómics!', 'success')
                return render_template('vistapago.html', plan=plan) # O a una página de confirmación
            except Error as e:
                flash(f'Error al procesar el pago o la suscripción: {e}', 'danger')
                conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

    return render_template('vistapago.html', plan=plan)

# --- Rutas de Dashboard de Editorial ---

@app.route('/editorial_dashboard')
@editorial_required
def editorial_dashboard():
    editorial_id = session.get('editorial_id')
    editorial_name = session.get('editorial_name')
    if not editorial_id:
        flash('No se encontró la editorial asociada a tu cuenta.', 'danger')
        return redirect(url_for('login'))

    comics_count = 0
    characters_count = 0
    all_comics = []

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Contar cómics de la editorial
            cursor.execute("SELECT COUNT(*) AS count FROM Comic WHERE id_editorial = %s", (editorial_id,))
            comics_result = cursor.fetchone()
            comics_count = comics_result['COUNT(*)'] if comics_result and 'COUNT(*)' in comics_result else 0

            # Contar personajes de la editorial
            cursor.execute("SELECT COUNT(*) AS count FROM Personaje WHERE id_editorial = %s", (editorial_id,))
            characters_result = cursor.fetchone()
            characters_count = characters_result['COUNT(*)'] if characters_result and 'COUNT(*)' in characters_result else 0

            # Obtener todos los cómics de la editorial
            cursor.execute("SELECT codigo_de_barras, titulo, autor, portada, fecha_publicacion FROM Comic WHERE id_editorial = %s ORDER BY titulo ASC", (editorial_id,))
            comics_data = cursor.fetchall()
            for comic in comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                all_comics.append(comic)

        except Error as e:
            flash(f"Error al cargar el panel de editorial: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('editorial_dashboard.html',
                           comics_count=comics_count,
                           characters_count=characters_count,
                           all_comics=all_comics,
                           editorial_name=editorial_name)


# --- Rutas de Carga de Cómics para Editoriales (Usando Tickets HTMLs) ---

@app.route('/editorial/upload/marvel', methods=['GET', 'POST'])
@editorial_required
def editorial_upload_marvel():
    current_editorial_id = session.get('editorial_id')
    # Usar get_editorial_id_flexible para obtener el ID de Marvel
    marvel_editorial_id = get_editorial_id_flexible(['Marvel Comics', 'Marvel'])

    if not marvel_editorial_id:
        flash('Error: Editorial "Marvel Comics" no encontrada en la base de datos.', 'danger')
        return redirect(url_for('editorial_dashboard'))

    if current_editorial_id != marvel_editorial_id:
        flash('No tienes permiso para subir cómics a la editorial Marvel.', 'danger')
        return redirect(url_for('editorial_dashboard'))

    top_comics = []
    bottom_comics = []
    all_characters = [] # Para la selección de personajes

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Cómics más vistos de Marvel
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) IN ('marvel comics', 'marvel')
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count DESC, c.titulo ASC
                LIMIT 5
            """)
            top_comics_data = cursor.fetchall()
            for comic in top_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                top_comics.append(comic)

            # Cómics menos vistos de Marvel
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) IN ('marvel comics', 'marvel')
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count ASC, c.titulo ASC
                LIMIT 5
            """)
            bottom_comics_data = cursor.fetchall()
            for comic in bottom_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                bottom_comics.append(comic)

            # Obtener todos los personajes para la selección (FILTRADO POR EDITORIAL)
            cursor.execute("SELECT id_personaje, nombre FROM Personaje WHERE id_editorial = %s ORDER BY nombre ASC", (marvel_editorial_id,))
            all_characters = cursor.fetchall()

        except Error as e:
            flash(f"Error al cargar datos para la subida de cómics de Marvel: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if request.method == 'POST':
        form_type = request.form.get('form_type') # Obtener el tipo de formulario

        if form_type == 'comic_upload':
            try:
                title = request.form['title']
                author = request.form['author']
                description = request.form['description']
                publication_date = request.form['publication_date']
                comic_code = request.form['comic_code']
                selected_character_ids = request.form.getlist('comic_characters') # Obtener la lista de IDs de personajes

                cover_file = request.files.get('cover_image')
                content_file = request.files.get('comic_content')

                portada_blob = cover_file.read() if cover_file else None
                contenido_blob = content_file.read() if content_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        # Insertar cómic
                        cursor.execute(
                            "INSERT INTO Comic (codigo_de_barras, titulo, autor, descripcion, id_editorial, fecha_publicacion, portada, contenido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (comic_code, title, author, description, current_editorial_id, publication_date, portada_blob, contenido_blob)
                        )
                        conn.commit()

                        # Insertar relaciones Comic-Personaje
                        if selected_character_ids:
                            for char_id in selected_character_ids:
                                cursor.execute(
                                    "INSERT INTO ComicPersonaje (codigo_de_barras, id_personaje) VALUES (%s, %s)",
                                    (comic_code, int(char_id))
                                )
                            conn.commit()

                        flash('Cómic de Marvel subido exitosamente por la editorial.', 'success')
                        return redirect(url_for('editorial_upload_marvel')) # Redirigir a la misma página para ver cambios
                    except Error as e:
                        flash(f'Error al subir el cómic de Marvel: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de cómic: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el cómic: {e}', 'danger')

        elif form_type == 'character_upload':
            try:
                name = request.form['name']
                description = request.form['description']
                image_file = request.files.get('character_image')

                imagen_blob = image_file.read() if image_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        # Asignar automáticamente a la editorial Marvel Comics
                        cursor.execute(
                            "INSERT INTO Personaje (nombre, descripcion, imagen, id_editorial) VALUES (%s, %s, %s, %s)",
                            (name, description, imagen_blob, marvel_editorial_id)
                        )
                        conn.commit()
                        flash('Personaje de Marvel subido exitosamente.', 'success')
                        return redirect(url_for('editorial_upload_marvel')) # Redirigir para recargar la página
                    except Error as e:
                        flash(f'Error al subir el personaje de Marvel: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de personaje: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el personaje: {e}', 'danger')
        else:
            flash('Tipo de formulario desconocido.', 'danger')

    return render_template('TicketsMarvel.html', top_comics=top_comics, bottom_comics=bottom_comics, all_characters=all_characters)


@app.route('/editorial/upload/dc', methods=['GET', 'POST'])
@editorial_required
def editorial_upload_dc():
    current_editorial_id = session.get('editorial_id')
    # Usar get_editorial_id_flexible para obtener el ID de DC
    dc_editorial_id = get_editorial_id_flexible(['DC Comics'])

    if not dc_editorial_id:
        flash('Error: Editorial "DC Comics" no encontrada en la base de datos.', 'danger')
        return redirect(url_for('editorial_dashboard'))

    if current_editorial_id != dc_editorial_id:
        flash('No tienes permiso para subir cómics a la editorial DC.', 'danger')
        return redirect(url_for('editorial_dashboard'))

    top_comics = []
    bottom_comics = []
    all_characters = [] # Para la selección de personajes

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Cómics más vistos de DC
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) = 'dc comics'
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count DESC, c.titulo ASC
                LIMIT 5
            """)
            top_comics_data = cursor.fetchall()
            for comic in top_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                top_comics.append(comic)

            # Cómics menos vistos de DC
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) = 'dc comics'
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count ASC, c.titulo ASC
                LIMIT 5
            """)
            bottom_comics_data = cursor.fetchall()
            for comic in bottom_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                bottom_comics.append(comic)

            # Obtener todos los personajes para la selección (FILTRADO POR EDITORIAL)
            cursor.execute("SELECT id_personaje, nombre FROM Personaje WHERE id_editorial = %s ORDER BY nombre ASC", (dc_editorial_id,))
            all_characters = cursor.fetchall()

        except Error as e:
            flash(f"Error al cargar datos para la subida de cómics de DC: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'comic_upload':
            try:
                comic_code = request.form['comic_code']
                title = request.form['title']
                author = request.form['author']
                description = request.form['description']
                publication_date = request.form['publication_date']
                selected_character_ids = request.form.getlist('comic_characters')

                cover_file = request.files.get('cover_image')
                content_file = request.files.get('comic_content')

                portada_blob = cover_file.read() if cover_file else None
                contenido_blob = content_file.read() if content_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "INSERT INTO Comic (codigo_de_barras, titulo, autor, descripcion, id_editorial, fecha_publicacion, portada, contenido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (comic_code, title, author, description, current_editorial_id, publication_date, portada_blob, contenido_blob)
                        )
                        conn.commit()

                        if selected_character_ids:
                            for char_id in selected_character_ids:
                                cursor.execute(
                                    "INSERT INTO ComicPersonaje (codigo_de_barras, id_personaje) VALUES (%s, %s)",
                                    (comic_code, int(char_id))
                                )
                            conn.commit()

                        flash('Cómic de DC subido exitosamente por la editorial.', 'success')
                        return redirect(url_for('editorial_upload_dc')) # Redirigir a la misma página para ver cambios
                    except Error as e:
                        flash(f'Error al subir el cómic de DC: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de cómic: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el cómic: {e}', 'danger')

        elif form_type == 'character_upload':
            try:
                name = request.form['name']
                description = request.form['description']
                image_file = request.files.get('character_image')

                imagen_blob = image_file.read() if image_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        # Asignar automáticamente a la editorial DC Comics
                        cursor.execute(
                            "INSERT INTO Personaje (nombre, descripcion, imagen, id_editorial) VALUES (%s, %s, %s, %s)",
                            (name, description, imagen_blob, dc_editorial_id)
                        )
                        conn.commit()
                        flash('Personaje de DC subido exitosamente.', 'success')
                        return redirect(url_for('editorial_upload_dc')) # Redirigir para recargar la página
                    except Error as e:
                        flash(f'Error al subir el personaje de DC: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de personaje: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el personaje: {e}', 'danger')
        else:
            flash('Tipo de formulario desconocido.', 'danger')

    return render_template('TicketsDC.html', top_comics=top_comics, bottom_comics=bottom_comics, all_characters=all_characters)

@app.route('/editorial/upload/indie', methods=['GET', 'POST'])
@editorial_required
def editorial_upload_indie():
    current_editorial_id = session.get('editorial_id')
    # Usar get_editorial_id_flexible para obtener el ID de Indie
    indie_editorial_id = get_editorial_id_flexible(['Indie Comics']) # Asumiendo una editorial 'Indie Comics'

    if not indie_editorial_id:
        flash('Error: Editorial "Indie Comics" no encontrada en la base de datos.', 'danger')
        return redirect(url_for('editorial_dashboard'))

    if current_editorial_id != indie_editorial_id:
        flash('No tienes permiso para subir cómics a la editorial Indie.', 'danger')
        return redirect(url_for('editorial_dashboard'))

    top_comics = []
    bottom_comics = []
    all_characters = [] # Para la selección de personajes

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Cómics más vistos de Indie
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) = 'indie comics'
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count DESC, c.titulo ASC
                LIMIT 5
            """)
            top_comics_data = cursor.fetchall()
            for comic in top_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                top_comics.append(comic)

            # Cómics menos vistos de Indie
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) = 'indie comics'
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count ASC, c.titulo ASC
                LIMIT 5
            """)
            bottom_comics_data = cursor.fetchall()
            for comic in bottom_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                bottom_comics.append(comic)

            # Obtener todos los personajes para la selección (FILTRADO POR EDITORIAL)
            cursor.execute("SELECT id_personaje, nombre FROM Personaje WHERE id_editorial = %s ORDER BY nombre ASC", (indie_editorial_id,))
            all_characters = cursor.fetchall()

        except Error as e:
            flash(f"Error al cargar datos para la subida de cómics Indie: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if request.method == 'POST':
        form_type = request.form.get('form_type') # Obtener el tipo de formulario

        if form_type == 'comic_upload':
            try:
                title = request.form['title']
                author = request.form['author']
                description = request.form['description']
                publication_date = request.form['publication_date']
                comic_code = request.form['comic_code']
                selected_character_ids = request.form.getlist('comic_characters') # Obtener la lista de IDs de personajes

                cover_file = request.files.get('cover_image')
                content_file = request.files.get('comic_content')

                portada_blob = cover_file.read() if cover_file else None
                contenido_blob = content_file.read() if content_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "INSERT INTO Comic (codigo_de_barras, titulo, autor, descripcion, id_editorial, fecha_publicacion, portada, contenido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (comic_code, title, author, description, current_editorial_id, publication_date, portada_blob, contenido_blob)
                        )
                        conn.commit()

                        # Insertar relaciones Comic-Personaje
                        if selected_character_ids:
                            for char_id in selected_character_ids:
                                cursor.execute(
                                    "INSERT INTO ComicPersonaje (codigo_de_barras, id_personaje) VALUES (%s, %s)",
                                    (comic_code, int(char_id))
                                )
                            conn.commit()

                        flash('Cómic Indie subido exitosamente por la editorial.', 'success')
                        return redirect(url_for('editorial_upload_indie')) # Redirigir a la misma página para ver cambios
                    except Error as e:
                        flash(f'Error al subir el cómic Indie: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de cómic: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el cómic: {e}', 'danger')
        else:
            flash('Tipo de formulario desconocido.', 'danger')

    return render_template('TicketsIndie.html', top_comics=top_comics, bottom_comics=bottom_comics, all_characters=all_characters)


# --- Rutas de Carga de Cómics por Administrador (Tickets) ---
# Estas rutas se mantienen para el usuario maestro, ya que tienen un rol distinto.

@app.route('/admin/upload/marvel', methods=['GET', 'POST'])
@admin_required
def admin_upload_marvel():
    # Usar get_editorial_id_flexible para obtener el ID de Marvel
    marvel_editorial_id = get_editorial_id_flexible(['Marvel Comics', 'Marvel'])
    if not marvel_editorial_id:
        flash('Error: Editorial "Marvel Comics" no encontrada en la base de datos. Por favor, asegúrate de que exista.', 'danger')
        return redirect(url_for('admin_dashboard'))

    top_comics = []
    bottom_comics = []
    all_characters = [] # Para la selección de personajes

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Cómics más vistos de Marvel
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) IN ('marvel comics', 'marvel')
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count DESC, c.titulo ASC
                LIMIT 5
            """)
            top_comics_data = cursor.fetchall()
            for comic in top_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                top_comics.append(comic)

            # Cómics menos vistos de Marvel
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) IN ('marvel comics', 'marvel')
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count ASC, c.titulo ASC
                LIMIT 5
            """)
            bottom_comics_data = cursor.fetchall()
            for comic in bottom_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                bottom_comics.append(comic)

            # Obtener todos los personajes para la selección (FILTRADO POR EDITORIAL)
            cursor.execute("SELECT id_personaje, nombre FROM Personaje WHERE id_editorial = %s ORDER BY nombre ASC", (marvel_editorial_id,))
            all_characters = cursor.fetchall()

        except Error as e:
            flash(f"Error al cargar datos para la subida de cómics de Marvel (Admin): {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if request.method == 'POST':
        form_type = request.form.get('form_type') # Obtener el tipo de formulario

        if form_type == 'comic_upload':
            try:
                title = request.form['title']
                author = request.form['author']
                description = request.form['description']
                publication_date = request.form['publication_date']
                comic_code = request.form['comic_code']
                selected_character_ids = request.form.getlist('comic_characters') # Obtener la lista de IDs de personajes

                cover_file = request.files.get('cover_image')
                content_file = request.files.get('comic_content')

                portada_blob = cover_file.read() if cover_file else None
                contenido_blob = content_file.read() if content_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "INSERT INTO Comic (codigo_de_barras, titulo, autor, descripcion, id_editorial, fecha_publicacion, portada, contenido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (comic_code, title, author, description, marvel_editorial_id, publication_date, portada_blob, contenido_blob)
                        )
                        conn.commit()

                        # Insertar relaciones Comic-Personaje
                        if selected_character_ids:
                            for char_id in selected_character_ids:
                                cursor.execute(
                                    "INSERT INTO ComicPersonaje (codigo_de_barras, id_personaje) VALUES (%s, %s)",
                                    (comic_code, int(char_id))
                                )
                            conn.commit()

                        flash('Cómic de Marvel subido exitosamente por el administrador.', 'success')
                        return redirect(url_for('admin_upload_marvel')) # Redirigir a la misma página para ver cambios
                    except Error as e:
                        flash(f'Error al subir el cómic de Marvel: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de cómic: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el cómic: {e}', 'danger')

        elif form_type == 'character_upload':
            try:
                name = request.form['name']
                description = request.form['description']
                image_file = request.files.get('character_image')

                imagen_blob = image_file.read() if image_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        # Asignar automáticamente a la editorial Marvel Comics
                        cursor.execute(
                            "INSERT INTO Personaje (nombre, descripcion, imagen, id_editorial) VALUES (%s, %s, %s, %s)",
                            (name, description, imagen_blob, marvel_editorial_id)
                        )
                        conn.commit()
                        flash('Personaje de Marvel subido exitosamente.', 'success')
                        return redirect(url_for('admin_upload_marvel')) # Redirigir para recargar la página
                    except Error as e:
                        flash(f'Error al subir el personaje de Marvel: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de personaje: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el personaje: {e}', 'danger')
        else:
            flash('Tipo de formulario desconocido.', 'danger')

    return render_template('TicketsMarvel.html', top_comics=top_comics, bottom_comics=bottom_comics, all_characters=all_characters)

@app.route('/admin/upload/dc', methods=['GET', 'POST'])
@admin_required
def admin_upload_dc():
    # Usar get_editorial_id_flexible para obtener el ID de DC
    dc_editorial_id = get_editorial_id_flexible(['DC Comics'])
    if not dc_editorial_id:
        flash('Error: Editorial "DC Comics" no encontrada en la base de datos. Por favor, asegúrate de que exista.', 'danger')
        return redirect(url_for('admin_dashboard'))

    top_comics = []
    bottom_comics = []
    all_characters = [] # Para la selección de personajes

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Cómics más vistos de DC
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) = 'dc comics'
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count DESC, c.titulo ASC
                LIMIT 5
            """)
            top_comics_data = cursor.fetchall()
            for comic in top_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                top_comics.append(comic)

            # Cómics menos vistos de DC
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) = 'dc comics'
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count ASC, c.titulo ASC
                LIMIT 5
            """)
            bottom_comics_data = cursor.fetchall()
            for comic in bottom_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                bottom_comics.append(comic)

            # Obtener todos los personajes para la selección (FILTRADO POR EDITORIAL)
            cursor.execute("SELECT id_personaje, nombre FROM Personaje WHERE id_editorial = %s ORDER BY nombre ASC", (dc_editorial_id,))
            all_characters = cursor.fetchall()

        except Error as e:
            flash(f"Error al cargar datos para la subida de cómics de DC (Admin): {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'comic_upload':
            try:
                comic_code = request.form['comic_code']
                title = request.form['title']
                author = request.form['author']
                description = request.form['description']
                publication_date = request.form['publication_date']
                selected_character_ids = request.form.getlist('comic_characters')

                cover_file = request.files.get('cover_image')
                content_file = request.files.get('comic_content')

                portada_blob = cover_file.read() if cover_file else None
                contenido_blob = content_file.read() if content_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "INSERT INTO Comic (codigo_de_barras, titulo, autor, descripcion, id_editorial, fecha_publicacion, portada, contenido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (comic_code, title, author, description, dc_editorial_id, publication_date, portada_blob, contenido_blob)
                        )
                        conn.commit()

                        if selected_character_ids:
                            for char_id in selected_character_ids:
                                cursor.execute(
                                    "INSERT INTO ComicPersonaje (codigo_de_barras, id_personaje) VALUES (%s, %s)",
                                    (comic_code, int(char_id))
                                )
                            conn.commit()

                        flash('Cómic de DC subido exitosamente por el administrador.', 'success')
                        return redirect(url_for('admin_upload_dc')) # Redirigir a la misma página para ver cambios
                    except Error as e:
                        flash(f'Error al subir el cómic de DC: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de cómic: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el cómic: {e}', 'danger')

        elif form_type == 'character_upload':
            try:
                name = request.form['name']
                description = request.form['description']
                image_file = request.files.get('character_image')

                imagen_blob = image_file.read() if image_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        # Asignar automáticamente a la editorial DC Comics
                        cursor.execute(
                            "INSERT INTO Personaje (nombre, descripcion, imagen, id_editorial) VALUES (%s, %s, %s, %s)",
                            (name, description, imagen_blob, dc_editorial_id)
                        )
                        conn.commit()
                        flash('Personaje de DC subido exitosamente.', 'success')
                        return redirect(url_for('admin_upload_dc')) # Redirigir para recargar la página
                    except Error as e:
                        flash(f'Error al subir el personaje de DC: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de personaje: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el personaje: {e}', 'danger')
        else:
            flash('Tipo de formulario desconocido.', 'danger')

    return render_template('TicketsDC.html', top_comics=top_comics, bottom_comics=bottom_comics, all_characters=all_characters)

@app.route('/admin/upload/indie', methods=['GET', 'POST'])
@admin_required
def admin_upload_indie():
    # Usar get_editorial_id_flexible para obtener el ID de Indie
    indie_editorial_id = get_editorial_id_flexible(['Indie Comics'])
    if not indie_editorial_id:
        flash('Error: Editorial "Indie Comics" no encontrada en la base de datos. Por favor, asegúrate de que exista.', 'danger')
        return redirect(url_for('admin_dashboard'))

    top_comics = []
    bottom_comics = []
    all_characters = [] # Para la selección de personajes

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Cómics más vistos de Indie
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) = 'indie comics'
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count DESC, c.titulo ASC
                LIMIT 5
            """)
            top_comics_data = cursor.fetchall()
            for comic in top_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                top_comics.append(comic)

            # Cómics menos vistos de Indie
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada, COUNT(hl.codigo_de_barras) AS view_count
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                LEFT JOIN HistorialLectura hl ON c.codigo_de_barras = hl.codigo_de_barras
                WHERE LOWER(e.nombre) = 'indie comics'
                GROUP BY c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.portada
                ORDER BY view_count ASC, c.titulo ASC
                LIMIT 5
            """)
            bottom_comics_data = cursor.fetchall()
            for comic in bottom_comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                bottom_comics.append(comic)

            # Obtener todos los personajes para la selección (FILTRADO POR EDITORIAL)
            cursor.execute("SELECT id_personaje, nombre FROM Personaje WHERE id_editorial = %s ORDER BY nombre ASC", (indie_editorial_id,))
            all_characters = cursor.fetchall()

        except Error as e:
            flash(f"Error al cargar datos para la subida de cómics Indie (Admin): {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if request.method == 'POST':
        form_type = request.form.get('form_type') # Obtener el tipo de formulario

        if form_type == 'comic_upload':
            try:
                title = request.form['title']
                author = request.form['author']
                description = request.form['description']
                publication_date = request.form['publication_date']
                comic_code = request.form['comic_code']
                selected_character_ids = request.form.getlist('comic_characters') # Obtener la lista de IDs de personajes

                cover_file = request.files.get('cover_image')
                content_file = request.files.get('comic_content')

                portada_blob = cover_file.read() if cover_file else None
                contenido_blob = content_file.read() if content_file else None

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "INSERT INTO Comic (codigo_de_barras, titulo, autor, descripcion, id_editorial, fecha_publicacion, portada, contenido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (comic_code, title, author, description, indie_editorial_id, publication_date, portada_blob, contenido_blob)
                        )
                        conn.commit()

                        # Insertar relaciones Comic-Personaje
                        if selected_character_ids:
                            for char_id in selected_character_ids:
                                cursor.execute(
                                    "INSERT INTO ComicPersonaje (codigo_de_barras, id_personaje) VALUES (%s, %s)",
                                    (comic_code, int(char_id))
                                )
                            conn.commit()

                        flash('Cómic Indie subido exitosamente por el administrador.', 'success')
                        return redirect(url_for('admin_upload_indie')) # Redirigir a la misma página para ver cambios
                    except Error as e:
                        flash(f'Error al subir el cómic Indie: {e}', 'danger')
                        conn.rollback()
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
            except KeyError as e:
                flash(f'Error al procesar el formulario de cómic: falta el campo {e}', 'danger')
            except Exception as e:
                flash(f'Ocurrió un error inesperado al subir el cómic: {e}', 'danger')
        else:
            flash('Tipo de formulario desconocido.', 'danger')

    return render_template('TicketsIndie.html', top_comics=top_comics, bottom_comics=bottom_comics, all_characters=all_characters)


# --- Ruta para Subir Personajes (Solo Admin) ---
@app.route('/admin/upload_character', methods=['GET', 'POST'])
@admin_required
def admin_upload_character():
    all_editorials = []
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id_editorial, nombre FROM Editorial ORDER BY nombre ASC")
            all_editorials = cursor.fetchall()
        except Error as e:
            flash(f"Error al cargar editoriales: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        editorial_id = request.form['editorial_id'] # Nuevo campo para la editorial
        image_file = request.files.get('character_image')

        imagen_blob = image_file.read() if image_file else None

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO Personaje (nombre, descripcion, imagen, id_editorial) VALUES (%s, %s, %s, %s)",
                    (name, description, imagen_blob, editorial_id)
                )
                conn.commit()
                flash('Personaje subido exitosamente.', 'success')
                return redirect(url_for('admin_dashboard')) # Redirigir al dashboard de admin
            except Error as e:
                flash(f'Error al subir el personaje: {e}', 'danger')
                conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
    return render_template('admin_upload_character_generic.html', all_editorials=all_editorials)

# --- Rutas CRUD para Editar y Eliminar (Solo Admin) ---

# Editar Cómic
@app.route('/admin/edit_comic/<int:comic_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_comic(comic_id):
    conn = get_db_connection()
    comic = None
    all_characters = []
    comic_characters = [] # Personajes ya asociados al cómic

    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Obtener detalles del cómic
            cursor.execute("""
                SELECT c.codigo_de_barras, c.titulo, c.autor, c.descripcion, c.fecha_publicacion, c.portada, c.contenido, c.id_editorial, e.nombre AS editorial_nombre
                FROM Comic c
                JOIN Editorial e ON c.id_editorial = e.id_editorial
                WHERE c.codigo_de_barras = %s
            """, (comic_id,))
            comic = cursor.fetchone()

            if comic:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                # No necesitamos el contenido BLOB para mostrar el formulario, solo para actualizarlo si se sube uno nuevo.
                # comic['contenido_b64'] = base64.b64encode(comic['contenido']).decode('utf-8') if comic['contenido'] else None

                # Obtener todos los personajes para la selección (FILTRADO POR LA EDITORIAL DEL CÓMIC)
                cursor.execute("SELECT id_personaje, nombre FROM Personaje WHERE id_editorial = %s ORDER BY nombre ASC", (comic['id_editorial'],))
                all_characters = cursor.fetchall()

                # Obtener personajes ya asociados a este cómic
                cursor.execute("""
                    SELECT p.id_personaje, p.nombre
                    FROM Personaje p
                    JOIN ComicPersonaje cp ON p.id_personaje = cp.id_personaje
                    WHERE cp.codigo_de_barras = %s
                """, (comic_id,))
                comic_characters = [char['id_personaje'] for char in cursor.fetchall()] # Solo los IDs

        except Error as e:
            flash(f"Error al cargar datos del cómic para edición: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if not comic:
        flash('Cómic no encontrado para edición.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        # Lógica para actualizar cómic
        title = request.form['title']
        author = request.form['author']
        description = request.form['description']
        publication_date = request.form['publication_date']
        selected_character_ids = request.form.getlist('comic_characters')

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                update_sql = "UPDATE Comic SET titulo = %s, autor = %s, descripcion = %s, fecha_publicacion = %s"
                update_params = [title, author, description, publication_date]

                cover_file = request.files.get('cover_image')
                if cover_file and cover_file.filename != '':
                    portada_blob = cover_file.read()
                    update_sql += ", portada = %s"
                    update_params.append(portada_blob)

                content_file = request.files.get('comic_content')
                if content_file and content_file.filename != '':
                    contenido_blob = content_file.read()
                    update_sql += ", contenido = %s"
                    update_params.append(contenido_blob)

                update_sql += " WHERE codigo_de_barras = %s"
                update_params.append(comic_id)

                cursor.execute(update_sql, tuple(update_params))

                # Actualizar relaciones Comic-Personaje
                cursor.execute("DELETE FROM ComicPersonaje WHERE codigo_de_barras = %s", (comic_id,))
                if selected_character_ids:
                    for char_id in selected_character_ids:
                        cursor.execute(
                            "INSERT INTO ComicPersonaje (codigo_de_barras, id_personaje) VALUES (%s, %s)",
                            (comic_id, int(char_id))
                        )
                conn.commit()
                flash('Cómic actualizado exitosamente.', 'success')
                return redirect(url_for('admin_dashboard'))
            except Error as e:
                flash(f'Error al actualizar el cómic: {e}', 'danger')
                conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
    return render_template('admin_edit_comic.html', comic=comic, all_characters=all_characters, comic_characters=comic_characters)

# Eliminar Cómic
@app.route('/admin/delete_comic/<int:comic_id>', methods=['POST'])
@admin_required
def admin_delete_comic(comic_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Eliminar registros relacionados primero (si hay FK ON DELETE RESTRICT/NO ACTION)
            cursor.execute("DELETE FROM HistorialLectura WHERE codigo_de_barras = %s", (comic_id,))
            cursor.execute("DELETE FROM Calificaciones WHERE codigo_de_barras = %s", (comic_id,))
            cursor.execute("DELETE FROM ComicPersonaje WHERE codigo_de_barras = %s", (comic_id,))

            # Eliminar el cómic
            cursor.execute("DELETE FROM Comic WHERE codigo_de_barras = %s", (comic_id,))
            conn.commit()
            flash('Cómic eliminado exitosamente.', 'success')
        except Error as e:
            flash(f'Error al eliminar el cómic: {e}', 'danger')
            conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return redirect(url_for('admin_dashboard'))

# Editar Personaje
@app.route('/admin/edit_character/<int:character_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_character(character_id):
    conn = get_db_connection()
    character = None
    all_editorials = [] # Para la selección de editorial

    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id_personaje, nombre, descripcion, imagen, id_editorial FROM Personaje WHERE id_personaje = %s", (character_id,))
            character = cursor.fetchone()
            if character and character['imagen']:
                character['imagen_b64'] = base64.b64encode(character['imagen']).decode('utf-8')

            cursor.execute("SELECT id_editorial, nombre FROM Editorial ORDER BY nombre ASC")
            all_editorials = cursor.fetchall()
        except Error as e:
            flash(f"Error al cargar datos del personaje para edición: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if not character:
        flash('Personaje no encontrado para edición.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        editorial_id = request.form['editorial_id'] # Nuevo campo para la editorial
        image_file = request.files.get('character_image')

        imagen_blob = image_file.read() if image_file else None

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                update_sql = "UPDATE Personaje SET nombre = %s, descripcion = %s, id_editorial = %s"
                update_params = [name, description, editorial_id]

                if image_file and image_file.filename != '':
                    imagen_blob = image_file.read()
                    update_sql += ", imagen = %s"
                    update_params.append(imagen_blob)

                update_sql += " WHERE id_personaje = %s"
                update_params.append(character_id)

                cursor.execute(update_sql, tuple(update_params))
                conn.commit()
                flash('Personaje actualizado exitosamente.', 'success')
                return redirect(url_for('admin_dashboard'))
            except Error as e:
                flash(f'Error al actualizar el personaje: {e}', 'danger')
                conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
    return render_template('admin_edit_character.html', character=character, all_editorials=all_editorials)

# Eliminar Personaje
@app.route('/admin/delete_character/<int:character_id>', methods=['POST'])
@admin_required
def admin_delete_character(character_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Eliminar registros relacionados primero (si hay FK ON DELETE RESTRICT/NO ACTION)
            cursor.execute("DELETE FROM Preferencias_usuario WHERE id_personaje = %s", (character_id,))
            cursor.execute("DELETE FROM ComicPersonaje WHERE id_personaje = %s", (character_id,))

            # Eliminar el personaje
            cursor.execute("DELETE FROM Personaje WHERE id_personaje = %s", (character_id,))
            conn.commit()
            flash('Personaje eliminado exitosamente.', 'success')
        except Error as e:
            flash(f'Error al eliminar el personaje: {e}', 'danger')
            conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return redirect(url_for('admin_dashboard'))

# --- Rutas de Dashboard de Administrador (Maestro) ---

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    users_count = 0
    editorials_count = 0
    comics_count = 0
    all_comics = []
    all_characters = []
    all_editorials = []
    all_users = []
    all_editorial_users = [] # Nueva variable para usuarios editoriales

    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Safely get counts, defaulting to 0 if no rows are returned
            cursor.execute("SELECT COUNT(*) FROM Usuario")
            users_result = cursor.fetchone()
            users_count = users_result['COUNT(*)'] if users_result and 'COUNT(*)' in users_result else 0

            cursor.execute("SELECT COUNT(*) FROM Editorial")
            editorials_result = cursor.fetchone()
            editorials_count = editorials_result['COUNT(*)'] if editorials_result and 'COUNT(*)' in editorials_result else 0

            cursor.execute("SELECT COUNT(*) FROM Comic")
            comics_result = cursor.fetchone()
            comics_count = comics_result['COUNT(*)'] if comics_result and 'COUNT(*)' in comics_result else 0

            # Obtener todos los cómics para la gestión
            cursor.execute("SELECT codigo_de_barras, titulo, autor, portada FROM Comic ORDER BY titulo ASC")
            comics_data = cursor.fetchall()
            for comic in comics_data:
                if comic['portada']:
                    comic['portada_b64'] = base64.b64encode(comic['portada']).decode('utf-8')
                else:
                    comic['portada_b64'] = None
                all_comics.append(comic)

            # Obtener todos los personajes para la gestión, incluyendo el nombre de la editorial
            cursor.execute("""
                SELECT p.id_personaje, p.nombre, p.imagen, e.nombre AS editorial_nombre
                FROM Personaje p
                LEFT JOIN Editorial e ON p.id_editorial = e.id_editorial
                ORDER BY p.nombre ASC
            """)
            characters_data = cursor.fetchall()
            for char in characters_data:
                if char['imagen']:
                    char['imagen_b64'] = base64.b64encode(char['imagen']).decode('utf-8')
                else:
                    char['imagen_b64'] = None
                all_characters.append(char)

            # Obtener todas las editoriales para la gestión
            cursor.execute("SELECT id_editorial, nombre FROM Editorial ORDER BY nombre ASC")
            all_editorials = cursor.fetchall()

            # Obtener todos los usuarios regulares para la gestión
            cursor.execute("SELECT correo_usuario, nombre, fecha_creacion FROM Usuario ORDER BY nombre ASC")
            all_users = cursor.fetchall()

            # NUEVO: Obtener todos los usuarios editoriales para la gestión
            cursor.execute("""
                SELECT ue.correo_editorial, ue.nombre, e.nombre AS editorial_nombre
                FROM Usuario_editorial ue
                JOIN Editorial e ON ue.id_editorial = e.id_editorial
                ORDER BY ue.nombre ASC
            """)
            all_editorial_users = cursor.fetchall()


        except Error as e:
            flash(f"Error al cargar estadísticas o datos de gestión: {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                    conn.close()
    return render_template('admin_dashboard.html',
                           users_count=users_count,
                           editorials_count=editorials_count,
                           comics_count=comics_count,
                           all_comics=all_comics,
                           all_characters=all_characters,
                           all_editorials=all_editorials,
                           all_users=all_users,
                           all_editorial_users=all_editorial_users) # Pasar los usuarios editoriales

# --- NUEVAS RUTAS: Gestión de Editoriales (Solo Admin) ---

@app.route('/admin/add_editorial', methods=['POST'])
@admin_required
def admin_add_editorial():
    if request.method == 'POST':
        editorial_name = request.form['editorial_name']
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO Editorial (nombre) VALUES (%s)", (editorial_name,))
                conn.commit()
                flash(f'Editorial "{editorial_name}" añadida exitosamente.', 'success')
            except Error as e:
                if e.errno == 1062: # Duplicate entry
                    flash(f'Error: La editorial "{editorial_name}" ya existe.', 'danger')
                else:
                    flash(f'Error al añadir la editorial: {e}', 'danger')
                conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_editorial', methods=['POST']) # Esta es la ruta correcta para actualizar via POST
@admin_required
def admin_update_editorial():
    if request.method == 'POST':
        editorial_id = request.form['editorial_id'] # Obtener ID del campo oculto
        new_name = request.form['new_editorial_name']
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE Editorial SET nombre = %s WHERE id_editorial = %s", (new_name, editorial_id))
                conn.commit()
                if cursor.rowcount > 0:
                    flash(f'Editorial actualizada a "{new_name}" exitosamente.', 'success')
                else:
                    flash('Editorial no encontrada para actualizar.', 'danger')
            except Error as e:
                if e.errno == 1062: # Duplicate entry
                    flash(f'Error: La editorial "{new_name}" ya existe.', 'danger')
                else:
                    flash(f'Error al actualizar la editorial: {e}', 'danger')
                conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_editorial/<int:editorial_id>', methods=['POST'])
@admin_required
def admin_delete_editorial(editorial_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Primero, desvincular personajes y cómics de esta editorial
            # Se asume que las FKs en Comic y Personaje tienen ON DELETE RESTRICT/NO ACTION,
            # o que se deben eliminar en cascada. Aquí, se eliminarán en cascada
            # los cómics y personajes asociados a la editorial para evitar errores de FK.

            # Eliminar relaciones Comic-Personaje para cómics de esta editorial
            cursor.execute("""
                DELETE cp FROM ComicPersonaje cp
                JOIN Comic c ON cp.codigo_de_barras = c.codigo_de_barras
                WHERE c.id_editorial = %s
            """, (editorial_id,))

            # Eliminar calificaciones de cómics de esta editorial
            cursor.execute("""
                DELETE cal FROM Calificaciones cal
                JOIN Comic c ON cal.codigo_de_barras = c.codigo_de_barras
                WHERE c.id_editorial = %s
            """, (editorial_id,))

            # Eliminar historial de lectura de cómics de esta editorial
            cursor.execute("""
                DELETE hl FROM HistorialLectura hl
                JOIN Comic c ON hl.codigo_de_barras = c.codigo_de_barras
                WHERE c.id_editorial = %s
            """, (editorial_id,))

            # Eliminar cómics de esta editorial
            cursor.execute("DELETE FROM Comic WHERE id_editorial = %s", (editorial_id,))

            # Eliminar preferencias de usuario asociadas a personajes de esta editorial
            cursor.execute("""
                DELETE pu FROM Preferencias_usuario pu
                JOIN Personaje p ON pu.id_personaje = p.id_personaje
                WHERE p.id_editorial = %s
            """, (editorial_id,))

            # Eliminar personajes de esta editorial
            cursor.execute("DELETE FROM Personaje WHERE id_editorial = %s", (editorial_id,))

            # Eliminar usuarios editoriales asociados a esta editorial
            cursor.execute("DELETE FROM Usuario_editorial WHERE id_editorial = %s", (editorial_id,))

            # Finalmente, eliminar la editorial
            cursor.execute("DELETE FROM Editorial WHERE id_editorial = %s", (editorial_id,))
            conn.commit()
            flash('Editorial y todos sus datos asociados eliminados exitosamente.', 'success')
        except Error as e:
            flash(f'Error al eliminar la editorial: {e}', 'danger')
            conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return redirect(url_for('admin_dashboard'))

# --- NUEVAS RUTAS: Gestión de Usuarios (Solo Admin) ---

@app.route('/admin/add_editorial_user', methods=['POST'])
@admin_required
def admin_add_editorial_user():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password = request.form['password']
        editorial_id = request.form['editorial_id']

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Formato de correo electrónico inválido.', 'danger')
            return redirect(url_for('admin_dashboard'))
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return redirect(url_for('admin_dashboard'))

        hashed_password = hash_password(password)
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                # INSERT CORRECTO para Usuario_editorial (sin fecha_registro)
                cursor.execute(
                    "INSERT INTO Usuario_editorial (correo_editorial, nombre, contraseña, id_editorial) VALUES (%s, %s, %s, %s)",
                    (email, name, hashed_password, editorial_id)
                )
                conn.commit()
                flash(f'Usuario editorial "{name}" añadido exitosamente para la editorial ID {editorial_id}.', 'success')
            except Error as e:
                if e.errno == 1062: # Duplicate entry
                    flash(f'Error: El correo electrónico "{email}" ya está registrado como usuario editorial.', 'danger')
                else:
                    flash(f'Error al añadir el usuario editorial: {e}', 'danger')
                conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<string:user_email>', methods=['POST'])
@admin_required
def admin_delete_user(user_email):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Eliminar registros relacionados primero (si hay FK ON DELETE RESTRICT/NO ACTION)
            cursor.execute("DELETE FROM HistorialLectura WHERE correo_usuario = %s", (user_email,))
            cursor.execute("DELETE FROM Calificaciones WHERE correo_usuario = %s", (user_email,))
            cursor.execute("DELETE FROM Preferencias_usuario WHERE correo_usuario = %s", (user_email,))
            cursor.execute("DELETE FROM Transacciones WHERE correo_usuario = %s", (user_email,))
            cursor.execute("DELETE FROM Suscripciones WHERE correo_usuario = %s", (user_email,))

            # Eliminar el usuario
            cursor.execute("DELETE FROM Usuario WHERE correo_usuario = %s", (user_email,))
            conn.commit()
            flash(f'Usuario "{user_email}" y todos sus datos asociados eliminados exitosamente.', 'success')
        except Error as e:
            flash(f'Error al eliminar el usuario: {e}', 'danger')
            conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return redirect(url_for('admin_dashboard'))

# NUEVA RUTA: Eliminar Usuario Editorial
@app.route('/admin/delete_editorial_user/<string:editorial_user_email>', methods=['POST'])
@admin_required
def admin_delete_editorial_user(editorial_user_email):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # No hay FKs complejas para Usuario_editorial, solo eliminar directamente
            cursor.execute("DELETE FROM Usuario_editorial WHERE correo_editorial = %s", (editorial_user_email,))
            conn.commit()
            flash(f'Usuario editorial "{editorial_user_email}" eliminado exitosamente.', 'success')
        except Error as e:
            flash(f'Error al eliminar el usuario editorial: {e}', 'danger')
            conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return redirect(url_for('admin_dashboard'))


# --- Ruta para la página de Videojuegos con verificación de suscripción ---
@app.route('/videojuegos')
@login_required # Asegura que el usuario esté logueado
def videojuegos():
    user_email = session['user_email']
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            # Verificar si el usuario tiene una suscripción "Anual Premium" (id_plan = 3) activa
            # y que la fecha de fin sea mayor o igual a la fecha actual
            cursor.execute("""
                SELECT * FROM Suscripciones
                WHERE correo_usuario = %s AND id_plan = 3 AND estado = 'Activa' AND fecha_fin >= CURDATE()
            """, (user_email,))
            premium_subscription = cursor.fetchone()

            if premium_subscription:
                # Si tiene la suscripción, renderiza el contenido de videojuegos.html
                return render_template('videojuegos.html')
            else:
                flash('Necesitas una suscripción "Anual Premium" activa para acceder a la sección de videojuegos.', 'warning')
                return redirect(url_for('subscriptions'))
    except Error as e:
        flash(f"Error al verificar la suscripción: {e}", 'danger')
        return redirect(url_for('home')) # Redirigir a inicio en caso de error de DB
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- NUEVA RUTA: Para servir los archivos HTML de juegos individuales ---
@app.route('/videojuegos/<string:game_name>')
@login_required
def play_game(game_name):
    user_email = session['user_email']
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            # Verificar si el usuario tiene una suscripción "Anual Premium" (id_plan = 3) activa
            cursor.execute("""
                SELECT * FROM Suscripciones
                WHERE correo_usuario = %s AND id_plan = 3 AND estado = 'Activa' AND fecha_fin >= CURDATE()
            """, (user_email,))
            premium_subscription = cursor.fetchone()

            if premium_subscription:
                # Si tiene la suscripción, renderiza el archivo HTML del juego desde la subcarpeta 'locura'
                # Flask buscará 'templates/locura/superman.html', 'templates/locura/spiderman1.html', etc.
                return render_template(f'locura/{game_name}')
            else:
                flash('Necesitas una suscripción "Anual Premium" activa para jugar a los videojuegos.', 'warning')
                return redirect(url_for('subscriptions'))
    except Exception as e:
        # Captura cualquier error, incluyendo TemplateNotFound si el archivo no existe
        flash(f"Error al cargar el juego: {e}. Asegúrate de que el archivo '{game_name}' exista en la carpeta 'templates/locura'.", 'danger')
        print(f"Error al cargar el juego '{game_name}': {e}") # Para depuración
        return redirect(url_for('videojuegos')) # Redirigir a la lista de juegos
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# --- Rutas de Errores ---

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

# 🚀 Arranque de la Aplicación
if __name__ == '__main__':
    app.run(debug=True)
