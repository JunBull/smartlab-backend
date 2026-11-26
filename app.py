import os
import re
import jwt
import psycopg2
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, jsonify, request
from flask_cors import CORS
from pypdf import PdfReader

app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"]
)

SECRET_KEY = os.getenv("SECRET_KEY", "clave-secreta-smartlab-2026")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

PDF_PATH = os.path.join(os.path.dirname(__file__), "pdf", "informacion.pdf")

# Estado global sincronizado con Wokwi, Vercel y Streamlit
iot_state = {
    "led": False,
    "modo_auto": False,
    "alerta_termica": False,
    "temperatura": 24.5,
    "humedad": 50.0,
    "actualizado_por": "sistema"
}

USUARIOS = {
    "admin": {"password": "admin123", "rol": "admin"},
    "juan": {"password": "juan123", "rol": "usuario"}
}

SECCIONES = {
    "climatizacion": "Protocolo de Climatización",
    "temperatura": "Protocolo de Climatización",
    "ventilador": "Protocolo de Climatización",
    "calor": "Protocolo de Climatización",
    "protocolo": "Protocolo de Climatización",
    "ciberseguridad": "Ingeniería en Ciberseguridad",
    "ingenieria en ciberseguridad": "Ingeniería en Ciberseguridad",
    "sistemas": "Ingeniería de Sistemas de Información",
    "ingenieria de sistemas": "Ingeniería de Sistemas de Información",
    "software": "Ingeniería de Software",
    "ingenieria de software": "Ingeniería de Software",
    "ciencia de datos": "Ciencia de Datos e Inteligencia Artificial",
    "inteligencia artificial": "Ciencia de Datos e Inteligencia Artificial",
}

def token_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"mensaje": "Token requerido"}), 401
        try:
            token = token.replace("Bearer ", "")
            datos = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"mensaje": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"mensaje": "Token inválido"}), 401
        return func(datos, *args, **kwargs)
    return decorated

def normalizar(texto):
    texto = texto.lower().strip()
    texto = re.sub(r"[¿?¡!.,;:]", " ", texto)
    for orig, dest in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]:
        texto = texto.replace(orig, dest)
    return re.sub(r"\s+", " ", texto)

def leer_pdf():
    if not os.path.exists(PDF_PATH):
        raise FileNotFoundError(f"No se encontró el PDF: {PDF_PATH}")
    lector = PdfReader(PDF_PATH)
    return "\n".join([(pagina.extract_text() or "") for pagina in lector.pages])

def extraer_secciones(texto):
    nombres = [
        "Protocolo de Climatización",
        "Ingeniería en Ciberseguridad",
        "Ingeniería de Sistemas de Información",
        "Ingeniería de Software",
        "Ciencia de Datos e Inteligencia Artificial",
        "Información institucional",
    ]
    posiciones = []
    for nombre in nombres:
        for coincidencia in re.finditer(re.escape(nombre), texto, re.IGNORECASE):
            posiciones.append((coincidencia.start(), nombre))
    posiciones.sort(key=lambda x: x[0])

    secciones = {}
    for indice, (inicio, nombre) in enumerate(posiciones):
        fin = posiciones[indice + 1][0] if indice + 1 < len(posiciones) else len(texto)
        secciones[nombre] = texto[inicio:fin].strip()
    return secciones

def detectar_seccion(pregunta):
    pregunta_norm = normalizar(pregunta)
    for clave, seccion in sorted(SECCIONES.items(), key=lambda x: len(x[0]), reverse=True):
        if clave in pregunta_norm:
            return seccion
    return None

def obtener_conexion():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require" if "supabase.com" in DB_HOST else "prefer"
    )

def guardar_conversacion(pregunta, respuesta):
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversaciones (pregunta, respuesta) VALUES (%s, %s)",
                (pregunta, respuesta),
            )
        conexion.commit()
        conexion.close()
    except Exception as e:
        print("Aviso BD chat:", e)

def registrar_telemetria(temp, hum, led):
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO mediciones_iot (temperatura, humedad, estado_led) VALUES (%s, %s, %s)",
                (temp, hum, led),
            )
        conexion.commit()
        conexion.close()
    except Exception as e:
        print("Aviso BD telemetría:", e)

# =====================================================
# RUTAS DE AUTENTICACIÓN Y ADMINISTRACIÓN
# =====================================================
@app.route("/", methods=["GET"])
def inicio():
    return jsonify({
        "aplicacion": "API SmartLab IoT Pro",
        "estado": "funcionando",
        "seguridad": ["HTTPS", "JWT", "RBAC", "CORS"]
    })

@app.route("/login", methods=["POST"])
def login():
    datos = request.get_json(silent=True) or {}
    usuario = str(datos.get("usuario", "")).strip()
    password = str(datos.get("password", "")).strip()

    if not usuario or not password:
        return jsonify({"mensaje": "Debe ingresar usuario y contraseña"}), 400
    if usuario not in USUARIOS or USUARIOS[usuario]["password"] != password:
        return jsonify({"mensaje": "Usuario o contraseña incorrectos"}), 401

    token = jwt.encode(
        {
            "usuario": usuario,
            "rol": USUARIOS[usuario]["rol"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=3)
        },
        SECRET_KEY,
        algorithm="HS256"
    )
    return jsonify({
        "mensaje": "Autenticación exitosa",
        "usuario": usuario,
        "rol": USUARIOS[usuario]["rol"],
        "token": token
    })

@app.route("/usuarios", methods=["GET"])
@token_required
def listar_usuarios(datos):
    if datos["rol"] != "admin":
        return jsonify({"mensaje": "Acceso denegado. Se requiere rol admin."}), 403
    lista = [{"usuario": k, "rol": v["rol"]} for k, v in USUARIOS.items()]
    return jsonify({"usuarios": lista})

# =====================================================
# RUTAS DE CONTROL IOT Y MODO AUTOMÁTICO
# =====================================================
@app.route("/led/status", methods=["GET"])
def led_status():
    return jsonify(iot_state)

@app.route("/led/on", methods=["POST"])
@token_required
def led_on(datos):
    if datos["rol"] != "admin":
        return jsonify({"mensaje": "Acceso denegado. Solo admin puede operar la ventilación."}), 403
    iot_state["led"] = True
    iot_state["modo_auto"] = False
    iot_state["actualizado_por"] = datos["usuario"]
    registrar_telemetria(iot_state["temperatura"], iot_state["humedad"], True)
    return jsonify({
        "success": True,
        "estado": iot_state,
        "message": f"Ventilación y compuerta ACTIVADAS por {datos['usuario']}"
    })

@app.route("/led/off", methods=["POST"])
@token_required
def led_off(datos):
    if datos["rol"] != "admin":
        return jsonify({"mensaje": "Acceso denegado. Solo admin puede operar la ventilación."}), 403
    iot_state["led"] = False
    iot_state["modo_auto"] = False
    iot_state["actualizado_por"] = datos["usuario"]
    registrar_telemetria(iot_state["temperatura"], iot_state["humedad"], False)
    return jsonify({
        "success": True,
        "estado": iot_state,
        "message": f"Ventilación y compuerta APAGADAS por {datos['usuario']}"
    })

@app.route("/led/toggle", methods=["POST"])
def led_toggle():
    # Endpoint usado por el botón físico del laboratorio en Wokwi
    iot_state["led"] = not iot_state["led"]
    iot_state["modo_auto"] = False
    iot_state["actualizado_por"] = "boton_esp32"
    registrar_telemetria(iot_state["temperatura"], iot_state["humedad"], iot_state["led"])
    return jsonify({
        "success": True,
        "estado": iot_state,
        "message": "Estado alternado desde el pulsador del laboratorio"
    })

@app.route("/modo/auto", methods=["POST"])
@token_required
def toggle_modo_auto(datos):
    if datos["rol"] != "admin":
        return jsonify({"mensaje": "Acceso denegado. Solo admin puede cambiar el modo."}), 403
    req = request.get_json(silent=True) or {}
    nuevo_modo = bool(req.get("activo", not iot_state["modo_auto"]))
    iot_state["modo_auto"] = nuevo_modo
    iot_state["actualizado_por"] = f"{datos['usuario']} (auto)"

    if nuevo_modo:
        if iot_state["temperatura"] > 28.0:
            iot_state["led"] = True
        elif iot_state["temperatura"] < 24.0:
            iot_state["led"] = False

    return jsonify({
        "success": True,
        "estado": iot_state,
        "message": "Modo Automático (>28°C) ACTIVADO" if nuevo_modo else "Modo Manual ACTIVADO"
    })

@app.route("/sensor/update", methods=["POST"])
def sensor_update():
    datos = request.get_json(silent=True) or {}
    if "temperatura" in datos:
        temp = float(datos["temperatura"])
        iot_state["temperatura"] = temp
        iot_state["alerta_termica"] = temp > 28.0

        # Lógica automática si está habilitada
        if iot_state["modo_auto"]:
            if temp > 28.0 and not iot_state["led"]:
                iot_state["led"] = True
                iot_state["actualizado_por"] = "auto_termico"
            elif temp < 24.0 and iot_state["led"]:
                iot_state["led"] = False
                iot_state["actualizado_por"] = "auto_termico"

    if "humedad" in datos:
        iot_state["humedad"] = float(datos["humedad"])

    registrar_telemetria(iot_state["temperatura"], iot_state["humedad"], iot_state["led"])
    return jsonify({"success": True, "estado": iot_state})

# =====================================================
# RUTAS DEL CHATBOT PDF Y SUPABASE
# =====================================================
@app.route("/chat", methods=["POST"])
def chat():
    datos = request.get_json(silent=True) or {}
    pregunta = str(datos.get("mensaje", "")).strip()
    if not pregunta:
        return jsonify({"error": "Debe enviar el campo 'mensaje'."}), 400
    try:
        texto_pdf = leer_pdf()
        secciones = extraer_secciones(texto_pdf)
        seccion = detectar_seccion(pregunta)

        if seccion is None:
            respuesta = (
                "No encontré una sección específica. Puedes consultar por:\n"
                "• Protocolo de Climatización\n"
                "• Ingeniería en Ciberseguridad\n"
                "• Ingeniería de Sistemas de Información\n"
                "• Ingeniería de Software\n"
                "• Ciencia de Datos e Inteligencia Artificial"
            )
        else:
            respuesta = "Según el manual oficial:\n\n" + secciones.get(seccion, "")

        guardar_conversacion(pregunta, respuesta)
        return jsonify({"pregunta": pregunta, "seccion": seccion, "respuesta": respuesta})
    except Exception as error:
        return jsonify({"error": str(error)}), 500

@app.route("/historial", methods=["GET"])
def historial():
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, pregunta, respuesta, fecha_hora FROM conversaciones ORDER BY id DESC LIMIT 10"
            )
            registros = cursor.fetchall()
        conexion.close()
        return jsonify([
            {
                "id": reg[0],
                "pregunta": reg[1],
                "respuesta": reg[2],
                "fecha_hora": reg[3].isoformat() if reg[3] else None
            }
            for reg in registros
        ])
    except Exception as error:
        return jsonify({"error": str(error)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
