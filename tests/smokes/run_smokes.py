import os
import time
import io
import json
from dataclasses import dataclass

import jwt
import requests
import psycopg
from PIL import Image


def env(name, default=None):
    return os.getenv(name, default)


@dataclass
class Seed:
    admin_id: int
    tech_id: int
    customer_id: int
    marca_id: int
    model_id: int
    acc_id: int


def pg_connect():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)


def seed_db() -> Seed:
    with pg_connect() as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        with conn.transaction():
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email=%s", ("smoke-admin@local",))
            row = cur.fetchone()
            if row:
                admin_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO users(nombre,email,rol,activo) VALUES (%s,%s,'jefe',true) RETURNING id",
                    ("Smoke Admin", "smoke-admin@local"),
                )
                admin_id = cur.fetchone()[0]

            cur.execute("SELECT id FROM users WHERE email=%s", ("smoke-tech@local",))
            row = cur.fetchone()
            if row:
                tech_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO users(nombre,email,rol,activo,perm_ingresar) VALUES (%s,%s,'tecnico',true,false) RETURNING id",
                    ("Smoke Tech", "smoke-tech@local"),
                )
                tech_id = cur.fetchone()[0]

            cur.execute("SELECT id FROM customers WHERE LOWER(razon_social)=LOWER(%s)", ("Smoke Customer",))
            row = cur.fetchone()
            if row:
                customer_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO customers(razon_social,cod_empresa) VALUES (%s,%s) RETURNING id",
                    ("Smoke Customer", "SMK"),
                )
                customer_id = cur.fetchone()[0]

            cur.execute("SELECT id FROM marcas WHERE UPPER(nombre)=UPPER(%s)", ("SmokeBrand",))
            row = cur.fetchone()
            if row:
                marca_id = row[0]
            else:
                cur.execute("INSERT INTO marcas(nombre) VALUES (%s) RETURNING id", ("SmokeBrand",))
                marca_id = cur.fetchone()[0]

            cur.execute(
                "SELECT id FROM models WHERE marca_id=%s AND UPPER(nombre)=UPPER(%s)", (marca_id, "SmokeModel")
            )
            row = cur.fetchone()
            if row:
                model_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO models(marca_id,nombre) VALUES (%s,%s) RETURNING id",
                    (marca_id, "SmokeModel"),
                )
                model_id = cur.fetchone()[0]

            cur.execute("SELECT id FROM catalogo_accesorios WHERE UPPER(nombre)=UPPER(%s)", ("Cargador",))
            row = cur.fetchone()
            if row:
                acc_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO catalogo_accesorios(nombre,activo) VALUES (%s,true) RETURNING id",
                    ("Cargador",),
                )
                acc_id = cur.fetchone()[0]

    return Seed(admin_id=admin_id, tech_id=tech_id, customer_id=customer_id, marca_id=marca_id, model_id=model_id, acc_id=acc_id)


def make_jwt(uid: int, role: str) -> str:
    secret = env("JWT_SECRET") or env("DJANGO_SECRET_KEY", "change-me")
    now = int(time.time())
    payload = {"uid": uid, "role": role, "iat": now, "exp": now + 7200}
    return jwt.encode(payload, secret, algorithm="HS256")


def base_url() -> str:
    url = env("API_URL") or f"http://{env('API_HOST','localhost')}:{env('API_PORT','18000')}"
    return url.rstrip("/") + "/api"


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def small_jpeg_bytes(w=64, h=64, color=(200, 80, 80)) -> bytes:
    buf = io.BytesIO()
    Image.new('RGB', (w, h), color=color).save(buf, format='JPEG')
    return buf.getvalue()


def run_flow():
    seed = seed_db()
    token = make_jwt(seed.admin_id, "jefe")
    tech_token = make_jwt(seed.tech_id, "tecnico")
    api = base_url()

    # 1) Ping
    r = requests.get(f"{api}/ping/")
    r.raise_for_status()

    # 2) Nuevo ingreso
    payload = {
        "cliente": {"id": seed.customer_id},
        "equipo": {"marca_id": seed.marca_id, "modelo_id": seed.model_id, "numero_interno": "SM-001"},
        "motivo": "reparacion",
        "informe_preliminar": "Equipo no enciende",
        "accesorios": "Cable, cargador",
    }
    r = requests.post(f"{api}/ingresos/nuevo/", json=payload, headers=auth_headers(token))
    r.raise_for_status()
    ingreso_id = r.json().get("id") or r.json().get("ingreso_id") or r.json().get("ingreso", {}).get("id")
    if not ingreso_id:
        raise RuntimeError("No se obtuvo ingreso_id del payload de respuesta")

    # 3) Asignar técnico (si aplica)
    requests.patch(
        f"{api}/ingresos/{ingreso_id}/",
        json={"asignado_a": seed.tech_id},
        headers=auth_headers(token),
    ).raise_for_status()

    # 4) Accesorios vinculados (catálogo y por ingreso)
    r = requests.get(f"{api}/accesorios/buscar/?ref=SM-001", headers=auth_headers(token))
    assert r.status_code in (200, 204)
    r = requests.post(
        f"{api}/ingresos/{ingreso_id}/accesorios/",
        json={"accesorio_id": seed.acc_id, "referencia": "pwr", "descripcion": "Cargador original"},
        headers=auth_headers(token),
    )
    r.raise_for_status()

    # 5) Subir media como técnico asignado
    files = {"files": ("foto.jpg", small_jpeg_bytes(), "image/jpeg")}
    r = requests.post(f"{api}/ingresos/{ingreso_id}/fotos/", files=files, headers=auth_headers(tech_token))
    r.raise_for_status()

    # 6) Agregar item de presupuesto, emitir y aprobar
    r = requests.post(
        f"{api}/quotes/{ingreso_id}/items/",
        json={"tipo": "mano_obra", "descripcion": "Diagnóstico y reparación", "qty": 1, "precio_u": 10000},
        headers=auth_headers(token),
    )
    r.raise_for_status()
    r = requests.post(f"{api}/quotes/{ingreso_id}/emitir/", json={}, headers=auth_headers(token))
    r.raise_for_status()
    r = requests.post(f"{api}/quotes/{ingreso_id}/aprobar/", json={}, headers=auth_headers(token))
    r.raise_for_status()

    # 7) Métricas básicas (no validamos mucho, solo 200)
    for path in ("metricas/resumen/", "metricas/series/", "metricas/config/"):
        requests.get(f"{api}/{path}", headers=auth_headers(token)).raise_for_status()

    # 8) Marcar reparado y entregar
    requests.post(f"{api}/ingresos/{ingreso_id}/reparado/", json={}, headers=auth_headers(tech_token)).raise_for_status()
    requests.post(
        f"{api}/ingresos/{ingreso_id}/entregar/",
        json={"remito_salida": "R-TEST-001", "factura_numero": "F0001-00000001"},
        headers=auth_headers(token),
    ).raise_for_status()

    # 9) Estado final del ingreso
    final = requests.get(f"{api}/ingresos/{ingreso_id}/", headers=auth_headers(token))
    final.raise_for_status()
    return {
        "ingreso_id": ingreso_id,
        "estado": final.json().get("estado"),
        "presupuesto_estado": final.json().get("presupuesto_estado"),
    }


if __name__ == "__main__":
    out = run_flow()
    print(json.dumps(out, ensure_ascii=False, indent=2))
