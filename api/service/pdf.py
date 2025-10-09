from io import BytesIO
from decimal import Decimal
from django.db import connection
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors
from django.conf import settings
from urllib.parse import quote
import os
import re
from datetime import datetime
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing

# Resolución: mapeo de valores internos -> etiqueta amigable
RESOLUTION_LABELS = {
    "reparado": "Reparado",
    "no_reparado": "No reparado",
    "no_se_encontro_falla": "No se encontró falla",
    "presupuesto_rechazado": "Presupuesto rechazado",
}

def resolution_label(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    return RESOLUTION_LABELS.get(v, v.replace("_", " ").capitalize())

# --- helpers de formato ---
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
DIAS  = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]

def fecha_larga(dt: datetime):
    d = dt
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month-1]} de {d.year}"

def money_es(v: Decimal) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")

def safe_name(s: str) -> str:
    s = s or ""
    s = re.sub(r"[^\w\s\.-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:80]

def _q(sql, params=None, one=False):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return (rows[0] if rows else None) if one else rows

def _get_data(ingreso_id: int):
    head = _q("""
        SELECT
            t.id AS ingreso_id,
            t.Resolucion,
            t.informe_preliminar,
            t.descripcion_problema,
            t.trabajos_realizados,
            t.accesorios,
            t.remito_ingreso,
            t.equipo_variante,
            t.motivo AS motivo,
            c.razon_social AS cliente,
            COALESCE(c.cuit, '') AS cliente_cuit,
            COALESCE(c.contacto, '') AS cliente_contacto,
            COALESCE(c.telefono, '') AS cliente_telefono,
            COALESCE(c.telefono_2, '') AS cliente_telefono_2,
            COALESCE(c.email, '') AS cliente_email,
            d.numero_serie,
            COALESCE(d.garantia_bool, false) AS garantia,
            COALESCE(b.nombre,'') AS marca,
            m.tipo_equipo as equipo,
            COALESCE(m.nombre,'') AS modelo,
            q.id AS quote_id, q.estado AS quote_estado, q.moneda,
            COALESCE(q.subtotal,0) AS subtotal,
            COALESCE(q.iva_21,0) AS iva_21,
            COALESCE(q.total,0) AS total,
            COALESCE(q.autorizado_por, 'Cliente') AS autorizado_por,
            COALESCE(q.forma_pago, '30 F.F.') AS forma_pago,
            COALESCE(q.fecha_emitido, NOW()) AS fecha_emitido
        FROM ingresos t
        JOIN devices d ON d.id=t.device_id
        JOIN customers c ON c.id=d.customer_id
        LEFT JOIN marcas b ON b.id=d.marca_id
        LEFT JOIN models m ON m.id=d.model_id
        LEFT JOIN quotes q ON q.ingreso_id=t.id
        WHERE t.id=%s
    """, [ingreso_id], one=True)

    items = _q("""
        SELECT descripcion, qty
        FROM quote_items qi
        JOIN quotes q ON q.id=qi.quote_id
        WHERE q.ingreso_id=%s
        ORDER BY qi.id
    """, [ingreso_id])

    # Accesorios normalizados -> construir texto amigable para el PDF
    accs = _q(
        """
          SELECT ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
          FROM ingreso_accesorios ia
          JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id AND ca.activo
          WHERE ia.ingreso_id=%s
          ORDER BY ia.id
        """,
        [ingreso_id]
    )
    if accs:
        lines = []
        for a in accs:
            name = (a.get("accesorio_nombre") or "").strip()
            ref  = (a.get("referencia") or "").strip()
            des  = (a.get("descripcion") or "").strip()
            parts = [name]
            if ref:
                parts.append(f"ref: {ref}")
            if des:
                parts.append(des)
            lines.append(" - "+" | ".join(parts))
        acc_text = "\n".join(lines)
        if not (head.get("accesorios") or "").strip():
            head["accesorios"] = acc_text
        else:
            head["accesorios"] = (head["accesorios"] or "").strip() + "\n" + acc_text

    return head, items


def _first_non_empty(*vals) -> str:
    for v in vals:
        s = ("" if v is None else str(v)).strip()
        if s:
            return s
    return ""


def _compose_equipment_label(head: dict) -> str:
    """Build a compact equipment label similar to web catalogEquipmentLabel.

    Prefers: Tipo | Marca | (Modelo + Variante)
    Falls back gracefully if some parts are missing.
    """
    tipo = _first_non_empty(head.get("tipo_equipo_nombre"), head.get("equipo"))
    marca = _first_non_empty(head.get("marca"))
    modelo = _first_non_empty(head.get("modelo"))
    variante = _first_non_empty(head.get("equipo_variante"))
    modelo_comp = (f"{modelo} {variante}" if modelo else variante).strip()
    parts = [p for p in (tipo, marca, modelo_comp) if p]
    return " | ".join(parts) if parts else _first_non_empty(head.get("equipo"), head.get("modelo"), head.get("marca"))


def _get_derivacion_data(ingreso_id: int, deriv_id: int | None = None) -> dict | None:
    """Fetch derivación data joined with ingreso/device/customer/model/provider.

    If deriv_id is None, use the latest derivación for the ingreso.
    """
    where = "WHERE ed.ingreso_id=%s"
    params: list = [ingreso_id]
    if deriv_id is not None:
        where += " AND ed.id=%s"
        params.append(deriv_id)
    sql = f"""
        SELECT
            t.id AS ingreso_id,
            COALESCE(c.razon_social,'') AS cliente,
            COALESCE(b.nombre,'') AS marca,
            COALESCE(m.nombre,'') AS modelo,
            m.tipo_equipo AS equipo,
            NULLIF(t.equipo_variante,'') AS equipo_variante,
            COALESCE(d.numero_serie,'') AS numero_serie,
            COALESCE(d.n_de_control,'') AS numero_interno,
            COALESCE(t.informe_preliminar,'') AS informe_preliminar,
            ed.id           AS deriv_id,
            COALESCE(ed.remit_deriv,'')    AS remit_deriv,
            ed.fecha_deriv  AS fecha_deriv,
            COALESCE(ed.comentarios,'')    AS comentarios,
            COALESCE(pe.nombre,'')         AS proveedor
        FROM equipos_derivados ed
        JOIN ingresos t   ON t.id = ed.ingreso_id
        JOIN devices d    ON d.id = t.device_id
        JOIN customers c  ON c.id = d.customer_id
        LEFT JOIN marcas b ON b.id = d.marca_id
        LEFT JOIN models m ON m.id = d.model_id
        LEFT JOIN proveedores_externos pe ON pe.id = ed.proveedor_id
        {where}
        ORDER BY ed.fecha_deriv DESC, ed.id DESC
        LIMIT 1
    """
    return _q(sql, params, one=True)


def render_remito_derivacion_pdf(ingreso_id: int, deriv_id: int | None = None, printed_by: str = ""):
    """Render two-section Derivación receipt (Original/Duplicado).

    Layout inspired by render_remito_salida_pdf, but simplified, no accessories, and
    emphasizing provider, reference, and comments.
    """
    head = _get_derivacion_data(ingreso_id, deriv_id)
    if not head:
        return b"", f"RemitoDerivacion_{ingreso_id}.pdf"

    empresa = _get_empresa_facturar(ingreso_id)
    _LOGO_THIS = _logo_path_for_company(empresa)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    W, H = A4
    margin = 12 * mm
    gap = 8 * mm
    ROW_H = 5 * mm
    ROW_GAP = 4.2 * mm
    SIGN_H = 5 * mm
    F_FIELD = 7.4
    F_LABEL = 6.8
    P_LH = 3.6 * mm

    usable_h = H - 2 * margin
    part_h = (usable_h - gap) / 2.0

    def draw_logo(x, y, w=24 * mm):
        candidates = []
        if _LOGO_THIS:
            candidates.append(_LOGO_THIS)
        env = os.environ.get("LOGO_PATH")
        if env:
            candidates.append(env)
        if LOGO_PATH:
            candidates.append(LOGO_PATH)
        candidates += [
            os.path.join(settings.BASE_DIR, "web", "public", "branding", "logo-empresa.png"),
            os.path.join(settings.BASE_DIR, "..", "web", "public", "branding", "logo-empresa.png"),
        ]
        for p in candidates:
            try:
                if p and os.path.exists(p):
                    c.drawImage(ImageReader(p), x, y, width=w, height=w/2.62, preserveAspectRatio=True, mask='auto')
                    return
            except Exception:
                continue

    def box(x, y, w, h):
        c.rect(x, y, w, h, stroke=1, fill=0)

    def label_value(x, y, w, h, label, value, fsz=F_FIELD, bold=False):
        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(x, y + h + 1.4 * mm, label)
        c.setFillColor(colors.black)
        box(x, y, w, h)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", fsz)
        c.drawString(x + 1.4 * mm, y + 1.2 * mm, str(value or "-"))

    def paragraph_in_box(x, y, w, h, title, text, fsz=F_FIELD):
        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(x, y + h + 1.4 * mm, title)
        c.setFillColor(colors.black)
        box(x, y, w, h)
        c.setFont("Helvetica", fsz)
        max_w = w - 3.6 * mm
        lines = _wrap_lines(text or "-", "Helvetica", fsz, max_w)
        ty = y + h - 3.0 * mm
        for ln in lines:
            if ty < y + 2.0 * mm:
                break
            c.drawString(x + 1.8 * mm, ty, ln)
            ty -= P_LH

    def big_title(y_top):
        x = margin + 6 * mm
        c.setFont("Helvetica", 10.2)
        title_txt = "Orden Interna de Servicio :"
        c.drawString(x, y_top - 5 * mm, title_txt)
        try:
            title_w = pdfmetrics.stringWidth(title_txt, "Helvetica", 10.2)
        except Exception:
            title_w = 75
        c.setFont("Helvetica-Bold", 12.8)
        c.drawString(x + title_w + 3 * mm, y_top - 5 * mm, f"{head['ingreso_id']}")
        # Subtítulo
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y_top - 12 * mm, "EQUIPO DERIVADO")
        # Logo
        draw_logo(W - margin - 26 * mm, y_top - 10 * mm, w=24 * mm)

    def field_grid(y_top, height):
        inner_x = margin + 6 * mm
        inner_w = W - 2 * margin - 12 * mm
        y = y_top - 18 * mm

        # r1: Derivado a | Fecha (sin remito/referencia)
        label_value(inner_x, y - ROW_H, 90 * mm, ROW_H, "Derivado a", head.get("proveedor"))
        label_value(inner_x + 92 * mm, y - ROW_H, 36 * mm, ROW_H, "Fecha",
                    (head.get("fecha_deriv") or datetime.now().date()).strftime("%d/%m/%y"), bold=True)
        y -= (ROW_H + ROW_GAP)

        # r2: Equipo (compose) | MG
        comp = _compose_equipment_label(head)
        label_value(inner_x, y - ROW_H, 110 * mm, ROW_H, "Equipo", comp)
        label_value(inner_x + 112 * mm, y - ROW_H, 30 * mm, ROW_H, "MG", head.get("numero_interno") or "")
        y -= (ROW_H + ROW_GAP)

        # r3: Marca | Modelo | NumeroSerie
        label_value(inner_x, y - ROW_H, 52 * mm, ROW_H, "Marca", head.get("marca"))
        label_value(inner_x + 54 * mm, y - ROW_H, 38 * mm, ROW_H, "Modelo", head.get("modelo"))
        label_value(inner_x + 95 * mm, y - ROW_H, 36 * mm, ROW_H, "NumeroSerie", head.get("numero_serie"))
        y -= (ROW_H + ROW_GAP)

        # r4: Informe preliminar
        paragraph_in_box(inner_x, y - 16 * mm, inner_w, 16 * mm, "Informe preliminar", head.get("informe_preliminar"))
        y -= (16 * mm + ROW_GAP)

        # r5: Observaciones (comentarios derivación)
        obs_h = 26 * mm
        paragraph_in_box(inner_x, y - obs_h, inner_w, obs_h, "Observaciones", head.get("comentarios"))
        y -= (obs_h + 7.6 * mm)

        # Firma y aclaración
        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(inner_x, y, "Recibido:")
        c.setFillColor(colors.black); box(inner_x + 18 * mm, y - (SIGN_H/2), 60 * mm, SIGN_H)
        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(inner_x + 88 * mm, y, "Aclaracion:")
        c.setFillColor(colors.black); box(inner_x + 110 * mm, y - (SIGN_H/2), 60 * mm, SIGN_H)

    def draw_form(y_top, height, leyenda):
        c.rect(margin, y_top - height, W - 2 * margin, height, stroke=1, fill=0)
        big_title(y_top)
        field_grid(y_top, height)
        c.setFont("Helvetica", 7.0)
        c.drawRightString(W - margin - 2 * mm, y_top - height + 3.5 * mm, leyenda)
        if printed_by:
            c.drawString(margin + 6 * mm, y_top - height + 3.5 * mm, f"Impreso por: {printed_by}")

    # Doble formulario: ORIGINAL y DUPLICADO
    y = H - margin
    draw_form(y, part_h, "ORIGINAL")
    y -= (part_h + gap)
    draw_form(y, part_h, "DUPLICADO")

    c.showPage(); c.save()
    pdf_bytes = buf.getvalue(); buf.close()
    return pdf_bytes, f"RemitoDerivacion_{ingreso_id}.pdf"

# Logo: detectar primera ruta disponible (permite logo-app.png)
def _detect_logo_path():
    env = os.environ.get("LOGO_PATH") or os.environ.get("SEPID_LOGO_PATH")
    candidates = [
        env,
        # rutas comunes en contenedor
        "/app/staticfiles/branding/logo-app.png",
        "/app/staticfiles/logo-app.png",
        "/app/staticfiles/logo.png",
        # rutas dentro del repo (dev local)
        os.path.join(settings.BASE_DIR, "web", "public", "branding", "logo-empresa.png"),
        os.path.join(settings.BASE_DIR, "web", "public", "branding", "logo-app.png"),
        os.path.join(settings.BASE_DIR, "..", "web", "public", "branding", "logo-empresa.png"),
        os.path.join(settings.BASE_DIR, "..", "web", "public", "branding", "logo-app.png"),
        os.path.join(settings.BASE_DIR, "service", "static", "logo-app.png"),
        os.path.join(settings.BASE_DIR, "service", "static", "logo.png"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

LOGO_PATH = _detect_logo_path()

# --- Empresa/branding helpers ---
def _get_empresa_facturar(ingreso_id: int) -> str:
    """Returns 'SEPID' (default) or 'MGBIO' from ingresos. Safe if column is missing."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                 WHERE table_name = 'ingresos'
                   AND column_name = 'empresa_facturar'
                   AND table_schema = ANY(current_schemas(true))
                 LIMIT 1
                """
            )
            exists = cur.fetchone() is not None
            if not exists:
                return "SEPID"
            cur.execute("SELECT empresa_facturar FROM ingresos WHERE id=%s", [ingreso_id])
            row = cur.fetchone()
            val = (row[0] if row else None) or "SEPID"
            return "MGBIO" if str(val).strip().upper() == "MGBIO" else "SEPID"
    except Exception:
        return "SEPID"


def _logo_path_for_company(code: str) -> str | None:
    """Return a best-effort path to a company logo that exists on disk.

    Tries environment overrides first, then common container/static paths,
    and finally repo-local development paths.
    """
    candidates: list[str | None] = []

    if code == "MGBIO":
        # override especí­fica para la segunda marca
        candidates.append(os.environ.get("LOGO_PATH_2"))
        # variantes habituales del nombre del archivo
        candidates += [
            "/app/staticfiles/branding/logo-empresa-2.png",
            "/app/staticfiles/logo-empresa-2.png",
            os.path.join(settings.BASE_DIR, "web", "public", "branding", "logo-empresa-2.png"),
            os.path.join(settings.BASE_DIR, "..", "web", "public", "branding", "logo-empresa-2.png"),
        ]

    # Comunes a cualquier marca
    candidates += [
        os.environ.get("LOGO_PATH"),
        LOGO_PATH,
        os.path.join(settings.BASE_DIR, "web", "public", "branding", "logo-empresa.png"),
        os.path.join(settings.BASE_DIR, "..", "web", "public", "branding", "logo-empresa.png"),
        "/app/staticfiles/branding/logo-app.png",
        "/app/staticfiles/logo-app.png",
        "/app/staticfiles/logo.png",
        os.path.join(settings.BASE_DIR, "service", "static", "logo-app.png"),
        os.path.join(settings.BASE_DIR, "service", "static", "logo.png"),
    ]

    for cand in candidates:
        try:
            if cand and os.path.exists(cand):
                return cand
        except Exception:
            continue
    return None


def _company_header_lines(code: str):
    """Returns (L1 address, L2 company name, L3 'CUIT ...') for given company code.

    Safe defaults are provided and variables are always defined to avoid runtime errors.
    """
    if code == "MGBIO":
        name = os.environ.get("COMPANY_NAME_2", "MG BIO")
        addr = os.environ.get("COMPANY_HEADER_L1_2") or os.environ.get("COMPANY_HEADER_L1", "")
        cuit = os.environ.get("COMPANY_FOOTER_CUIT_2", "")
        return addr, name, (f"CUIT {cuit}" if cuit else "")
    name = os.environ.get("COMPANY_NAME", "SEPID SA")
    addr = os.environ.get("COMPANY_HEADER_L1", "")
    cuit = os.environ.get("COMPANY_FOOTER_CUIT", "")
    return addr, name, (f"CUIT {cuit}" if cuit else "")

def _wrap_lines(text, font, size, max_width):
    """Corta texto por palabras para que entre en max_width."""
    text = (text or "").replace("\r", "")
    lines = []
    for raw_line in text.split("\n"):
        words = raw_line.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            trial = cur + " " + w
            if pdfmetrics.stringWidth(trial, font, size) <= max_width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines

def _draw_block(c, x, y, title, value, width, font="Helvetica", fsize=9, leading=12):
    """Dibuja un tí­tulo y un bloque multilí­nea sin detallar precios."""
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, title)
    y -= 4
    c.setLineWidth(0.5)
    c.line(x, y, x + width, y)
    y -= leading
    c.setFont(font, fsize)
    max_text_width = width
    for line in _wrap_lines(value or "â€”", font, fsize, max_text_width):
        c.drawString(x, y, line)
        y -= leading
    return y

def _draw_equipment_panel(c, x, y, w, marca, modelo, numero_serie, equipo=None, remito=None):
    h = 28 * mm
    c.setFillColor(colors.whitesmoke)
    c.roundRect(x, y - h, w, h, 4, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.roundRect(x, y - h, w, h, 4, stroke=1, fill=0)

    if equipo:
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9); c.drawString(x + 5*mm, y - 7*mm, f"Equipo: {equipo}")

    if remito:
        c.setFont("Helvetica", 9); c.drawString(w- 30*mm, y - 7*mm, "Remito Ingreso:")
        c.setFont("Helvetica", 9); c.drawString(w- 30*mm + 70, y - 7*mm, str(remito))

    col_w = w / 3.0 + 3*mm
    base_y = y - 14*mm

    def col(ix, label, value):
        cx = x + ix * col_w + 5*mm
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        c.drawString(cx, base_y, label)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(cx, base_y - 6*mm, value or "â€”")

    col(0, "Marca", (marca or "").upper())
    col(1, "Modelo", (modelo or "").upper())
    col(2, "Número de serie", (numero_serie or "").upper())
    return y - h - 8

def render_quote_pdf(ingreso_id: int):
    head, items = _get_data(ingreso_id)
    if not head:
        return None, None

    # Recalcular totales desde items (evita depender de quotes.subtotal desactualizado)
    try:
        row = _q(
            """
            SELECT COALESCE(SUM(qi.qty*qi.precio_u),0) AS subtotal
            FROM quote_items qi
            JOIN quotes q ON q.id=qi.quote_id
            WHERE q.ingreso_id=%s
            """,
            [ingreso_id],
            one=True,
        ) or {"subtotal": 0}
        subtotal_calc = Decimal(row.get("subtotal") or 0)
        iva_21_calc = subtotal_calc * Decimal("0.21")
        total_calc = subtotal_calc + iva_21_calc
        head["subtotal"], head["iva_21"], head["total"] = subtotal_calc, iva_21_calc, total_calc
    except Exception:
        pass

    # Empresa para logo/pie, pero los headers permanecen fijos como antes
    empresa = _get_empresa_facturar(ingreso_id)
    _LOGO_THIS = _logo_path_for_company(empresa)
    # Encabezado de empresa (fijo, indiferente de la empresa seleccionada)
    EMPRESA_LINEA1 = getattr(settings, "COMPANY_HEADER_L1", "Valdenegro 4578 C.A.B.A (1430)")
    EMPRESA_LINEA2 = getattr(settings, "COMPANY_HEADER_L2", "IMPORTADORES DE EQUIPOS")
    EMPRESA_LINEA3 = getattr(settings, "COMPANY_HEADER_L3", "MEDICOS Y REPARACIONES")

    cliente_display = (head.get("cliente") or "Cliente").strip()
    os_label = f"OS {str(head['ingreso_id']).zfill(6)}"
    title = f"{os_label} {cliente_display}".strip()
    filename = f"{safe_name(title)}.pdf"

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(title)
    W, H = A4

    ml, mt = 18*mm, 18*mm
    y = H - mt

    # logo en encabezado
    # Logo: intentar por empresa y si falla usar el global
    _logo_candidates = []
    if _LOGO_THIS:
        _logo_candidates.append(_LOGO_THIS)
    if LOGO_PATH:
        _logo_candidates.append(LOGO_PATH)
    for _lp in _logo_candidates:
        if _lp and os.path.exists(_lp):
            try:
                logo_w = 50 * mm
                x_logo = W/3 - logo_w
                c.drawImage(
                    ImageReader(_lp),
                    x_logo, y - 15*mm,
                    width=logo_w,
                    height=logo_w/2.62,
                    preserveAspectRatio=True,
                    mask='auto'
                )
                break
            except Exception:
                continue

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(W - W/3+5*mm, y-4*mm, EMPRESA_LINEA2)
    c.drawCentredString(W - W/3+5*mm, y-9*mm, EMPRESA_LINEA3)
    c.setFont("Helvetica", 9)
    c.drawCentredString(W - W/3+5*mm, y-14*mm, EMPRESA_LINEA1)

    # Tí­tulo de OS a la derecha, debajo del encabezado de empresa
    c.setFont("Helvetica-Bold", 18)
    y_title = y - 25*mm
    c.drawCentredString(W/2, y_title, title)

    # Separación suficiente para no superponer con encabezado/tí­tulo
    y -= 27 *mm
    c.setLineWidth(0.8)
    c.line(ml, y, W-ml, y)
    y -= 10

    c.setFont("Helvetica", 11)
    c.drawString(ml, y, f"Señor(es): {head['cliente']}")
    y -= 16

    # Datos adicionales del cliente
    try:
        c.setFont("Helvetica", 10)
        cuit_val = (head.get("cliente_cuit") or "").strip() or "-"
        c.drawString(ml, y, f"CUIT: {cuit_val}")
        y -= 14
        parts = []
        contacto = (head.get("cliente_contacto") or "").strip()
        tel1 = (head.get("cliente_telefono") or "").strip()
        tel2 = (head.get("cliente_telefono_2") or "").strip()
        email = (head.get("cliente_email") or "").strip()
        if contacto:
            parts.append(f"Contacto: {contacto}")
        tel = " / ".join([p for p in [tel1, tel2] if p])
        if tel:
            parts.append(f"Tel: {tel}")
        if email:
            parts.append(f"Email: {email}")
        if parts:
            c.drawString(ml, y, "   ".join(parts))
            y -= 16
    except Exception:
        pass

    y = _draw_equipment_panel(
        c, ml, y, W - 2*ml,
        head.get("marca"), head.get("modelo"), head.get("numero_serie"),
        equipo=head.get("equipo"),remito = head.get("remito_ingreso"),
    )

    y -= 5
    if head.get("informe_preliminar"):
        y = _draw_block(c, ml, y, "Info. preliminar", head["informe_preliminar"], W-2*ml) - 6
    if head.get("accesorios"):
        y = _draw_block(c, ml, y, "Accesorios", head["accesorios"], W-2*ml) - 6



    y -= 15

    mats = []
    seen = set()
    for it in items or []:
        d = (it.get("descripcion") or "").strip()
        if not d:
            continue
        d_up = d.upper()
        if d_up not in seen:
            seen.add(d_up)
            mats.append(d_up)
    mat_text = "\n".join(mats) if mats else "-"
    # Se eliminó la sección "Mat. Reemplazar"
    # y = _draw_block(c, ml, y, "Mat. Reemplazar", mat_text, W-2*ml) - 4

    diag = (head.get("descripcion_problema") or "").strip()
    trab = (head.get("trabajos_realizados") or "").strip()
    diag_trab = (diag + ("\n" if diag and trab else "") + trab) or "â€”"
    y = _draw_block(c, ml, y, "Detalle Rep. (Diagnóstico / Trabajos a realizar)", diag_trab, W-2*ml) - 2

    y -= 6
    c.setLineWidth(0.6); c.line(ml, y, W-ml, y); y -= 10
    c.setFont("Helvetica", 10)
    c.drawRightString(ml + 140*mm, y, "Total Neto :")
    c.drawRightString(W - ml, y, f"$ {money_es(Decimal(head['subtotal']))}")
    y -= 14
    c.drawRightString(ml + 140*mm, y, "IVA:")
    c.drawRightString(W - ml, y, f"$ {money_es(Decimal(head['iva_21']))}")
    y -= 14
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(ml + 140*mm, y, "Total:")
    c.drawRightString(W - ml, y, f"$ {money_es(Decimal(head['total']))}")
    y -= 18

    c.setFont("Helvetica", 10)
    forma_pago = head.get("forma_pago") or "30 F.F."
    c.drawString(ml, y, f"FormaPago: {forma_pago}"); y -= 12
    c.drawString(ml, y, "PlazoEntrega: INMEDIATA"); y -= 12
    c.drawString(ml, y, "Garantia: 90 DÍAS"); y -= 12
    c.drawString(ml, y, "Mant. de Oferta: 7 DÍAS"); y -= 18

    fecha = fecha_larga(head["fecha_emitido"])
    c.drawString(ml, y, fecha); y -= 18
    c.drawString(ml, y, "Atte. Serv.Técnico"); y -= 14
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(ml, y, "Ante cualquier duda esperamos su llamado")

    # --- Pie de página con datos de contacto (sin alterar layout superior) ---
    try:
        footer_email = getattr(settings, "COMPANY_FOOTER_EMAIL", None)
        footer_web = getattr(settings, "COMPANY_FOOTER_WEB", None)
        footer_wa = getattr(settings, "COMPANY_FOOTER_WHATSAPP", None)
        parts = []
        if footer_email:
            parts.append(footer_email)
        if footer_web:
            parts.append(footer_web)
        if footer_wa:
            parts.append(f"WhatsApp: {footer_wa}")
        if parts:
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.grey)
            c.drawCentredString(W/2, 10*mm, " | ".join(parts))
            c.setFillColor(colors.black)
    except Exception:
        # Nunca romper el render del PDF por el pie de página
        pass

    c.showPage()
    c.save()
    pdf = buf.getvalue(); buf.close()
    return filename, pdf  # <- MISMA FIRMA QUE TENÍAS

def _fetchone_dict(cur):
    row = cur.fetchone()
    if not row:
        return None
    cols = [c[0] for c in cur.description]
    return dict(zip(cols, row))

# =========================
# ORDEN DE SALIDA / REMITO
# =========================
def render_remito_salida_pdf(ingreso_id: int, printed_by: str = ""):
    """
    Orden de salida en 3 franjas (proporción 2â€“2â€“1).
    Cajas de 5 mm de alto y separación vertical (ROW_GAP) aumentada +3 mm para evitar solapes.
    """
    head, _items = _get_data(ingreso_id)
    if not head:
        return b"", f"Remito_{ingreso_id}.pdf"

    # Recalculate totals from items to avoid stale quote data
    try:
        row = _q(
            """
            SELECT COALESCE(SUM(qi.qty*qi.precio_u),0) AS subtotal
            FROM quote_items qi
            JOIN quotes q ON q.id=qi.quote_id
            WHERE q.ingreso_id=%s
            """,
            [ingreso_id],
            one=True,
        ) or {"subtotal": 0}
        subtotal_calc = Decimal(row.get("subtotal") or 0)
        iva_21_calc = subtotal_calc * Decimal("0.21")
        total_calc = subtotal_calc + iva_21_calc
        head["subtotal"], head["iva_21"], head["total"] = subtotal_calc, iva_21_calc, total_calc
    except Exception:
        # Si falla el calculo, continuamos con los valores existentes
        pass

    empresa = _get_empresa_facturar(ingreso_id)
    L1, L2, L3 = _company_header_lines(empresa)
    _LOGO_THIS = _logo_path_for_company(empresa)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # --- Geometrí­a A4 ---
    W, H = A4
    margin = 12 * mm
    gap = 6 * mm
    GRID_DOWN = 5 * mm  # bajar grilla medio cm

    usable_h = H - 2 * margin
    part = (usable_h - 2 * gap) / 5.0      # 5 partes -> 2-2-1
    h_each_form = 2 * part
    h_label     = 1 * part

    # ---- Dimensiones de campos ----
    ROW_H   = 5 * mm          # alto de las cajas
    ROW_GAP = 4.4 * mm        # <<< antes ~1.4mm; +3mm para más aire
    SIGN_H  = 5 * mm          # alto caja de firma
    F_FIELD = 7.4             # fuente dentro de las cajas
    F_LABEL = 6.8             # fuente de etiquetas
    P_LH    = 3.6 * mm        # leading de párrafo en Observaciones

    def draw_logo(x, y, w=24 * mm):
        # Probar varias rutas posibles para aumentar la robustez
        candidates = []
        if _LOGO_THIS:
            candidates.append(_LOGO_THIS)
        candidates.append(os.environ.get("LOGO_PATH"))
        if LOGO_PATH:
            candidates.append(LOGO_PATH)
        # rutas dentro del repo por si el env está mal configurado en dev
        candidates += [
            os.path.join(settings.BASE_DIR, "web", "public", "branding", "logo-empresa.png"),
            os.path.join(settings.BASE_DIR, "..", "web", "public", "branding", "logo-empresa.png"),
        ]
        for p in candidates:
            try:
                if p and os.path.exists(p):
                    c.drawImage(ImageReader(p), x, y, width=w, height=w/2.62,
                                preserveAspectRatio=True, mask='auto')
                    return
            except Exception:
                continue

    def box(x, y, w, h):
        c.rect(x, y, w, h, stroke=1, fill=0)

    def label_value(x, y, w, h, label, value, fsz=F_FIELD, bold=False):
        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(x, y + h + 1.4 * mm, label)
        c.setFillColor(colors.black)
        box(x, y, w, h)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", fsz)
        c.drawString(x + 1.4 * mm, y + 1.2 * mm, str(value or "-"))

    def paragraph_in_box(x, y, w, h, title, text, fsz=F_FIELD):
        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(x, y + h + 1.4 * mm, title)
        c.setFillColor(colors.black)
        box(x, y, w, h)
        c.setFont("Helvetica", fsz)
        max_w = w - 3.6 * mm
        lines = _wrap_lines(text or "-", "Helvetica", fsz, max_w)
        ty = y + h - 3.0 * mm
        for ln in lines:
            if ty < y + 2.0 * mm:
                break
            c.drawString(x + 1.8 * mm, ty, ln)
            ty -= P_LH

    def big_title(y_top):
        x = margin + 6 * mm
        # Tí­tulo y número de OS juntos
        c.setFont("Helvetica", 10.2)
        title_txt = "Orden Interna de Servicio :"
        c.drawString(x, y_top - 5 * mm, title_txt)
        # Calcular ancho del tí­tulo para ubicar el número pegado a la derecha
        try:
            title_w = pdfmetrics.stringWidth(title_txt, "Helvetica", 10.2)
        except Exception:
            title_w = 75  # fallback aproximado
        c.setFont("Helvetica-Bold", 12.8)
        c.drawString(x + title_w + 3 * mm, y_top - 5 * mm, f"{head['ingreso_id']}")

        # Logo arriba a la derecha (sin nombre de empresa ni dirección para evitar solapes)
        draw_logo(W - margin - 26 * mm, y_top - 10 * mm, w=24 * mm)

        # No dibujar nombre ni dirección; opcionalmente podrí­a mostrarse el CUIT si se desea.
        # Lo omitimos para asegurar que no tape los campos superiores.

        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x, y_top - 11.5 * mm, "ENTREGA DE EQUIPO")

    def field_grid(y_top, height):
        inner_x = margin + 6 * mm
        inner_w = W - 2 * margin - 12 * mm

        header_h = 10 * mm
        footer_h = 5 * mm
        content_h = height - header_h - footer_h

        # punto inicial (bajado) para la grilla
        y = y_top - header_h - 2 * mm - GRID_DOWN

        # alto de Observaciones ajustado al nuevo ROW_GAP
        obs_h = max(
            9 * mm,
            content_h - GRID_DOWN - (ROW_H + ROW_GAP) * 3 - SIGN_H - 7 * mm
        )

        # r1: Cliente | Fecha | Prop.
        label_value(inner_x, y - ROW_H, 74 * mm, ROW_H, "Cliente", head.get("cliente"))
        label_value(inner_x + 76 * mm, y - ROW_H, 25 * mm, ROW_H, "Fecha",
                    datetime.now().strftime("%d/%m/%y"), bold=True)
        label_value(inner_x + 104 * mm, y - ROW_H, 36 * mm, ROW_H, "Prop.",
                    head.get("propietario_nombre") or "")
        y -= (ROW_H + ROW_GAP)

        # r2: Equipo | Marca | Modelo | NumeroSerie
        label_value(inner_x, y - ROW_H, 52 * mm, ROW_H, "Equipo", head.get("equipo"))
        label_value(inner_x + 54 * mm, y - ROW_H, 38 * mm, ROW_H, "Marca", head.get("marca"))
        label_value(inner_x + 95 * mm, y - ROW_H, 36 * mm, ROW_H, "Modelo", head.get("modelo"))
        label_value(inner_x + 134 * mm, y - ROW_H, 36 * mm, ROW_H, "NumeroSerie", head.get("numero_serie"))
        y -= (ROW_H + ROW_GAP)

        # r3: Accesorios | Garantia | Resolucion
        label_value(inner_x, y - ROW_H, 102 * mm, ROW_H, "Accesorios", head.get("accesorios"))
        garantia_txt = "Si" if head.get("garantia") else "No"
        label_value(inner_x + 104 * mm, y - ROW_H, 24 * mm, ROW_H, "Garantia", garantia_txt  )
        label_value(inner_x + 131 * mm, y - ROW_H, 39 * mm, ROW_H, "Resolucion", resolution_label(head.get("resolucion")))
        y -= (ROW_H + ROW_GAP)

        # Observaciones (Descripción + Trabajos)
        obs_txt = " \n\n Trabajos realizados:\n ".join(
            [t for t in [(head.get("descripcion_problema") or "").strip(),
                         (head.get("trabajos_realizados") or "").strip()] if t]
        ) or "-"
        paragraph_in_box(inner_x, y - obs_h, inner_w, obs_h, "Observaciones", obs_txt)
        y -= (obs_h + 2.6 * mm)

        # Firma y costo
        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(inner_x, y, "Recibido:")
        c.setFillColor(colors.black); box(inner_x + 18 * mm, y - (SIGN_H/2), 60 * mm, SIGN_H)

        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(inner_x + 118 * mm, y, "Costo Neto:")
        # Draw box and value for net cost (subtotal)
        x_box = inner_x + 138 * mm
        w_box = 24 * mm
        y_box = y - (SIGN_H/2)
        c.setFillColor(colors.black)
        box(x_box, y_box, w_box, SIGN_H)
        try:
            neto_val = Decimal(head.get("subtotal") or 0)
        except Exception:
            neto_val = Decimal(0)
        c.setFont("Helvetica-Bold", F_FIELD)
        c.drawRightString(x_box + w_box - 1.4 * mm, y_box + 1.2 * mm, f"$ {money_es(neto_val)}")

    def draw_form(y_top, height, leyenda):
        c.rect(margin, y_top - height, W - 2 * margin, height, stroke=1, fill=0)
        big_title(y_top)
        field_grid(y_top, height)
        c.setFont("Helvetica", 7.0)
        c.drawRightString(W - margin - 2 * mm, y_top - height + 3.5 * mm, leyenda)
        if printed_by:
            c.drawString(margin + 6 * mm, y_top - height + 3.5 * mm, f"Impreso por: {printed_by}")

    def draw_label(y_top, height):
        c.setDash(3, 2)
        c.line(margin, y_top, W - margin, y_top)
        c.setDash()
        c.rect(margin, y_top - height, W - 2 * margin, height, stroke=1, fill=0)
        x = margin + 6 * mm
        y = y_top - 10 * mm

        # Logo en la esquina superior derecha del recuadro de etiqueta
        draw_logo(W - margin - 26 * mm, y_top - 10 * mm, w=24 * mm)

        c.setFont("Helvetica-Bold", 13.0); c.drawString(x, y, f"OS {head['ingreso_id']}")
        y -= 8.5 * mm
        c.setFont("Helvetica", 10.0)
        c.drawString(x, y, f"Cliente: {head.get('cliente') or '-'}"); y -= 6.5 * mm
        c.drawString(x, y, f"NúmeroSerie: {head.get('numero_serie') or '-'}"); y -= 6.5 * mm
        c.drawString(x, y, f"Equipo: {_compose_equipment_label(head) or (head.get('equipo') or '-')}"); y -= 10 * mm

        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(x, y, "Recibido:")
        c.setFillColor(colors.black); box(x + 18 * mm, y - (SIGN_H/2), 60 * mm, SIGN_H)

        c.setFont("Helvetica", F_LABEL); c.setFillColor(colors.grey)
        c.drawString(x + 118 * mm, y, "Costo Neto:")
        # Draw box and value for net cost (subtotal)
        x_box = x + 138 * mm
        w_box = 24 * mm
        y_box = y - (SIGN_H/2)
        c.setFillColor(colors.black)
        box(x_box, y_box, w_box, SIGN_H)
        try:
            neto_val = Decimal(head.get("subtotal") or 0)
        except Exception:
            neto_val = Decimal(0)
        c.setFont("Helvetica-Bold", F_FIELD)
        c.drawRightString(x_box + w_box - 1.4 * mm, y_box + 1.2 * mm, f"$ {money_es(neto_val)}")

        base = getattr(settings, 'PUBLIC_WEB_URL', '').rstrip('/')
        url = f"{base}/ingresos/{head['ingreso_id']}"
        code = qr.QrCodeWidget(url)
        d = Drawing(60, 60); d.add(code)
        # Correr el QR a la izquierda para no superponer con el logo
        renderPDF.draw(d, c, W - margin - 80 * mm, y_top - height + 20 * mm)

    # --- 2â€“2â€“1 ---
    y = H - margin
    draw_form(y, h_each_form, "ORIGINAL")
    y -= (h_each_form + gap)
    draw_form(y, h_each_form, "DUPLICADO")
    y -= (h_each_form + gap)
    draw_label(y, h_label)

    c.showPage(); c.save()
    pdf_bytes = buf.getvalue(); buf.close()
    return pdf_bytes, f"Remito_{ingreso_id}.pdf"







