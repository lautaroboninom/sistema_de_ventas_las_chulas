#!/usr/bin/env python3
"""
Apply de base de datos para servidores:
- Ejecuta migraciones Django (incluye service.0013_db_apply_probe_marker)
- Verifica que el cambio de schema se haya aplicado

Uso recomendado (servidor Docker):
  python apply.py

Uso local (sin Docker):
  python apply.py --local
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TARGET_APP = "service"
TARGET_MIGRATION = "0013_db_apply_probe_marker"


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)


def docker_compose_cmd(compose_file: str, *tail: str) -> list[str]:
    return ["docker", "compose", "-f", compose_file, *tail]


def run_docker_apply(compose_file: str) -> None:
    run(
        docker_compose_cmd(
            compose_file,
            "exec",
            "-T",
            "api",
            "python",
            "manage.py",
            "migrate",
            TARGET_APP,
            TARGET_MIGRATION,
            "--noinput",
        )
    )
    run(
        docker_compose_cmd(
            compose_file,
            "exec",
            "-T",
            "api",
            "python",
            "manage.py",
            "migrate",
            "--noinput",
        )
    )
    verification_code = (
        "from django.db import connection; "
        "cur = connection.cursor(); "
        "cur.execute(\"\"\""
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_name = 'retail_settings' "
        "  AND column_name = 'db_apply_probe_marker' "
        "\"\"\"); "
        "column_ok = bool(cur.fetchone()); "
        "cur.execute(\"\"\""
        "SELECT db_apply_probe_marker "
        "FROM retail_settings "
        "WHERE id = 1"
        "\"\"\"); "
        "row = cur.fetchone(); "
        "marker = row[0] if row else None; "
        "print(f'column_ok={column_ok}'); "
        "print(f'marker={marker}')"
    )
    run(
        docker_compose_cmd(
            compose_file,
            "exec",
            "-T",
            "api",
            "python",
            "manage.py",
            "shell",
            "-c",
            verification_code,
        )
    )


def run_local_apply(repo_root: Path) -> None:
    api_dir = repo_root / "api"
    run(
        [
            sys.executable,
            "manage.py",
            "migrate",
            TARGET_APP,
            TARGET_MIGRATION,
            "--noinput",
        ],
        cwd=api_dir,
    )
    run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=api_dir)
    verification_code = (
        "from django.db import connection; "
        "cur = connection.cursor(); "
        "cur.execute(\"\"\""
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_name = 'retail_settings' "
        "  AND column_name = 'db_apply_probe_marker' "
        "\"\"\"); "
        "column_ok = bool(cur.fetchone()); "
        "cur.execute(\"\"\""
        "SELECT db_apply_probe_marker "
        "FROM retail_settings "
        "WHERE id = 1"
        "\"\"\"); "
        "row = cur.fetchone(); "
        "marker = row[0] if row else None; "
        "print(f'column_ok={column_ok}'); "
        "print(f'marker={marker}')"
    )
    run([sys.executable, "manage.py", "shell", "-c", verification_code], cwd=api_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply de DB para RetailHub.")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Ejecuta migrate localmente sobre api/manage.py (sin Docker).",
    )
    parser.add_argument(
        "--compose-file",
        default="docker-compose.prod.yml",
        help="Archivo compose para entorno servidor (default: docker-compose.prod.yml).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    try:
        if args.local:
            run_local_apply(repo_root)
        else:
            run_docker_apply(args.compose_file)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: el apply fallo (exit code {exc.returncode}).")
        return exc.returncode

    print("OK: apply DB completado.")
    print(
        "Nota: despues de hacer pull en otra maquina/servidor, correr este apply para "
        "aplicar cambios de DB."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

