from flask import Flask, render_template
import mysql.connector

app = Flask(__name__)

# 🔌 Conexión a MySQL
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='1234',
        database='SofiaComics'
    )

# 🧭 Rutas principales
@app.route('/')
def home():
    return render_template('TicketsMarvel.html')

@app.route('/cuenta')
def cuenta():
    return render_template('CreacionDeCuenta.html')

@app.route('/tickets/marvel')
def tickets_marvel():
    return render_template('TicketsMarvel.html')

@app.route('/tickets/dc')
def tickets_dc():
    return render_template('TicketsDC.html')

@app.route('/suscripcion')
def suscripcion():
    return render_template('Suscripcion.html')

@app.route('/skins')
def skins_gratis():
    return render_template('skinsgratis.html')

@app.route('/formulario')
def formulario():
    return render_template('formulario.html')

@app.route('/precomic')
def precomic():
    return render_template('precomic.html')

@app.route('/vistapago')
def vistapago():
    return render_template('vistapago.html')

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

# 🚀 Arranque
if __name__ == '__main__':
    app.run(debug=True)
