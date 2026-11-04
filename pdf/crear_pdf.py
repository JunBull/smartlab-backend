from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ARCHIVO = "informacion.pdf"

def crear_pdf():
    documento = SimpleDocTemplate(
        ARCHIVO,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Manual SmartLab IoT - USIL",
        author="SmartLab Team",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("Titulo", parent=estilos["Title"], alignment=TA_CENTER, fontSize=16, leading=20, spaceAfter=10)
    subtitulo = ParagraphStyle("Subtitulo", parent=estilos["Heading2"], fontSize=12, leading=15, spaceBefore=10, spaceAfter=6)
    texto = ParagraphStyle("Texto", parent=estilos["BodyText"], fontSize=9.5, leading=13, spaceAfter=6)

    contenido = []
    contenido.append(Paragraph("FACULTAD DE INGENIERÍA E INTELIGENCIA ARTIFICIAL", titulo))
    contenido.append(Paragraph("Protocolos de Climatización y Guía de Operaciones", subtitulo))
    contenido.append(Paragraph("Documento técnico de consulta rápida para el sistema de soporte automatizado.", texto))
    contenido.append(Spacer(1, 8))

    tabla_datos = [
        [Paragraph("<b>Sección</b>", texto), Paragraph("<b>Procedimiento Operativo</b>", texto)],
        [Paragraph("Protocolo de Climatización", texto), Paragraph("Si la temperatura supera 28 °C, activar ventilación. Al descender de 24 °C, apagar para ahorrar energía.", texto)],
        [Paragraph("Ingeniería en Ciberseguridad", texto), Paragraph("Aplica cifrado HTTPS, tokens JWT y control de acceso RBAC para proteger el acceso a los actuadores.", texto)],
        [Paragraph("Ingeniería de Sistemas de Información", texto), Paragraph("Gestiona el flujo de datos entre sensores, bases de datos PostgreSQL y paneles analíticos.", texto)],
        [Paragraph("Ingeniería de Software", texto), Paragraph("Diseño de la API en Flask, arquitectura modular de microservicios y contenedorización con Docker.", texto)],
        [Paragraph("Ciencia de Datos e Inteligencia Artificial", texto), Paragraph("Monitoreo estadístico de temperatura y procesamiento de lenguaje para el asistente virtual.", texto)],
    ]
    tabla = Table(tabla_datos, colWidths=[60 * mm, 105 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    contenido.append(tabla)
    contenido.append(Spacer(1, 10))

    secciones = [
        ("Protocolo de Climatización", "La temperatura operativa estándar debe oscilar entre 20 °C y 24 °C. Si los sensores reportan más de 28 °C en el laboratorio de cómputo, el operador debe encender la ventilación (LED en pin GPIO 2). El sistema se apagará una vez estabilizado el ambiente."),
        ("Ingeniería en Ciberseguridad", "Los comandos críticos del sistema requieren el rol 'admin'. El uso de tokens JWT previene modificaciones no autorizadas en el estado de los actuadores del ESP32."),
        ("Ingeniería de Sistemas de Información", "La infraestructura se apoya en Supabase para almacenar el histórico de eventos y permitir la auditoría remota de las órdenes enviadas."),
        ("Ingeniería de Software", "El código sigue una separación por capas: presentación en Vercel, lógica en Render, base de datos en Supabase y hardware en MicroPython."),
        ("Ciencia de Datos e Inteligencia Artificial", "El chatbot extrae respuestas directas del archivo PDF sin recurrir a inferencias no documentadas, asegurando fiabilidad técnica."),
        ("Información institucional", "Para incidentes mayores o soporte de hardware, acudir a la oficina técnica de la Facultad de Ingeniería de la USIL.")
    ]
    for nom, desc in secciones:
        contenido.append(Paragraph(nom, subtitulo))
        contenido.append(Paragraph(desc, texto))

    documento.build(contenido)
    print("PDF creado con éxito.")

if __name__ == "__main__":
    crear_pdf()
