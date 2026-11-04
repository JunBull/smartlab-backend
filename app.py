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
CORS(app, resources={r"/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"], methods=["GET", "POST", "OPTIONS"])

SECRET_KEY = os.getenv("SECRET_KEY", "smartlab-secret-key-2026")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

PDF_PATH = os.path.join(os.path.dirname(__file__), "pdf", "informacion.pdf")

iot_state = {
    "led": False,
    "temperatura": 23.5,
    "humedad": 52.0,
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
    "ciberseguridad": "Ingeniería en Ciberseguridad",
    "sistemas": "Ingeniería de Sistemas de Información",
    "software": "Ingeniería de Software",
    "datos": "Ciencia de Datos e Inteligencia Artificial",
    "inteligencia artificial": "Ciencia de Datos e Inteligencia Artificial"
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
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({"mensaje": "Token inválido o expirado"}), 401
        return func(datos, *args, **kwargs)
    return decorated

def normalizar(texto):
    texto = texto.lower().strip()
    texto = re.sub(r"[¿?¡!.,;:]", " ", texto)
    for origen, destino in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]:
        texto = texto.replace(origen, destino)
    return re.sub(r"\s+", " ", texto)

def leer_pdf():
    if not os.path.exists(PDF_PATH):
        raise FileNotFoundError(f"No existe el archivo {PDF_PATH}")
    lector = PdfReader(PDF_PATH)
    return "\n".join([(pagina.extract_text() or "") for pagina in lector.pages])

def extraer_secciones(texto):
    titulos = [
        "Protocolo de Climatización",
        "Ingeniería en Ciberseguridad",
        "Ingeniería de Sistemas de Información",
        "Ingeniería de Software",
        "Ciencia de Datos e Inteligencia Artificial",
        "Información institucional"
    ]
    pos = []
    for t in titulos:
        for match in re.finditer(re.escape(t), texto, re.IGNORECASE):
            pos.append((match.start(), t))
    pos.sort(key=lambda x: x[0])
    resultado = {}
    for i, (inicio, titulo) in enumerate(pos):
        fin = pos[i + 1][0] if i + 1 < len(pos) else len(texto)
        resultado[titulo] = texto[inicio:fin].strip()
    return resultado

def detectar_seccion(pregunta):
    preg = normalizar(pregunta)
    for clave, seccion in sorted(SECCIONES.items(), key=lambda x: len(x[0]), reverse=True):
        if clave in preg:
            return seccion
    return None

def obtener_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require" if "supabase.com" in DB_HOST else "prefer"
    )

def guardar_chat(pregunta, respuesta):
    try:
        conn = obtener_db()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO conversaciones (pregunta, respuesta) VALUES (%s, %s)", (pregunta, respuesta))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Error al guardar chat:", e)

def registrar_telemetria(temp, hum, led):
    try:
        conn = obtener_db()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO mediciones_iot (temperatura, humedad, estado_led) VALUES (%s, %s, %s)", (temp, hum, led))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Error al registrar telemetría:", e)

@app.route("/", methods=["GET"])
def inicio():
    return jsonify({"sistema": "SmartLab IoT API", "estado": "activo"})

@app.route("/login", methods=["POST"])
def login():
    datos = request.get_json(silent=True) or {}
    usr = str(datos.get("usuario", "")).strip()
    pwd = str(datos.get("password", "")).strip()
    if usr not in USUARIOS or USUARIOS[usr]["password"] != pwd:
        return jsonify({"mensaje": "Credenciales inválidas"}), 401
    token = jwt.encode(
        {"usuario": usr, "rol": USUARIOS[usr]["rol"], "exp": datetime.now(timezone.utc) + timedelta(hours=3)},
        SECRET_KEY,
        algorithm="HS256"
    )
    return jsonify({"mensaje": "Acceso correcto", "usuario": usr, "rol": USUARIOS[usr]["rol"], "token": token})

@app.route("/perfil", methods=["GET"])
@token_required
def perfil(datos):
    return jsonify({"usuario": datos["usuario"], "rol": datos["rol"]})

@app.route("/usuarios", methods=["GET"])
@token_required
def usuarios(datos):
    if datos["rol"] != "admin":
        return jsonify({"mensaje": "Acceso denegado. Se requiere rol admin."}), 403
    return jsonify({"usuarios": list(USUARIOS.keys())})

@app.route("/led/status", methods=["GET"])
def get_led():
    return jsonify(iot_state)

@app.route("/led/on", methods=["POST"])
@token_required
def post_led_on(datos):
    if datos["rol"] != "admin":
        return jsonify({"mensaje": "Acceso denegado. Rol admin requerido."}), 403
    iot_state["led"] = True
    iot_state["actualizado_por"] = datos["usuario"]
    registrar_telemetria(iot_state["temperatura"], iot_state["humedad"], True)
    return jsonify({"success": True, "led": True, "message": f"Ventilación activada por {datos['usuario']}"})

@app.route("/led/off", methods=["POST"])
@token_required
def post_led_off(datos):
    if datos["rol"] != "admin":
        return jsonify({"mensaje": "Acceso denegado. Rol admin requerido."}), 403
    iot_state["led"] = False
    iot_state["actualizado_por"] = datos["usuario"]
    registrar_telemetria(iot_state["temperatura"], iot_state["humedad"], False)
    return jsonify({"success": True, "led": False, "message": f"Ventilación apagada por {datos['usuario']}"})

@app.route("/sensor/update", methods=["POST"])
def sensor_update():
    datos = request.get_json(silent=True) or {}
    if "temperatura" in datos and "humedad" in datos:
        iot_state["temperatura"] = float(datos["temperatura"])
        iot_state["humedad"] = float(datos["humedad"])
        registrar_telemetria(iot_state["temperatura"], iot_state["humedad"], iot_state["led"])
    return jsonify({"success": True, "estado": iot_state})

@app.route("/chat", methods=["POST"])
def chat():
    datos = request.get_json(silent=True) or {}
    preg = str(datos.get("mensaje", "")).strip()
    if not preg:
        return jsonify({"error": "Debe enviar un mensaje"}), 400
    try:
        texto = leer_pdf()
        secciones = extraer_secciones(texto)
        seccion = detectar_seccion(preg)
        if seccion:
            resp = "Según el manual:\n\n" + secciones.get(seccion, "")
        else:
            resp = "No encontré un procedimiento para esa consulta. Puedes preguntar por Climatización, Ciberseguridad, Software o Sistemas."
        guardar_chat(preg, resp)
        return jsonify({"pregunta": preg, "seccion": seccion, "respuesta": resp})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/historial", methods=["GET"])
def historial():
    try:
        conn = obtener_db()
        with conn.cursor() as cur:
            cur.execute("SELECT id, pregunta, respuesta, fecha_hora FROM conversaciones ORDER BY id DESC LIMIT 15")
            filas = cur.fetchall()
        conn.close()
        return jsonify([{"id": r[0], "pregunta": r[1], "respuesta": r[2], "fecha_hora": r[3].isoformat() if r[3] else None} for r in filas])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
