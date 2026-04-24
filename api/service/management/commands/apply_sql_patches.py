from __future__ import annotations

import hashlib
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


PATCHES_TABLE = "retail_db_applies"
PATCHES_DIR_ENV = "DB_APPLY_SCRIPTS_DIR"
PATCHES_ENABLED_ENV = "DB_APPLY_SCRIPTS_ENABLED"
ADVISORY_LOCK_KEY = 81426047


class Command(BaseCommand):
    help = (
        "Aplica archivos SQL pendientes en orden de nombre, "
        "registrando hash por archivo para evitar re-aplicaciones."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            dest="patches_dir",
            default="",
            help=(
                "Directorio de scripts SQL a aplicar. "
                "Default: env DB_APPLY_SCRIPTS_DIR o <api>/sql/applies "
                "(fallback <repo>/sql/applies)."
            ),
        )

    def handle(self, *args, **options):
        if not self._enabled():
            self.stdout.write("DB apply SQL: omitido por DB_APPLY_SCRIPTS_ENABLED=0.")
            return

        patches_dir = self._resolve_patches_dir(options.get("patches_dir") or "")
        if not patches_dir.exists():
            self.stdout.write(
                f"DB apply SQL: directorio no encontrado ({patches_dir}). Nada para aplicar."
            )
            return
        if not patches_dir.is_dir():
            raise CommandError(f"DB apply SQL: la ruta no es directorio: {patches_dir}")

        scripts = sorted(p for p in patches_dir.glob("*.sql") if p.is_file())
        if not scripts:
            self.stdout.write(f"DB apply SQL: sin scripts pendientes en {patches_dir}.")
            return

        self._acquire_lock()
        try:
            self._ensure_registry_table()
            applied = 0
            skipped = 0

            for script_path in scripts:
                script_name = script_path.name
                script_text = self._read_script(script_path)
                if not script_text.strip():
                    self.stdout.write(
                        self.style.WARNING(f"DB apply SQL: script vacio, se omite: {script_name}")
                    )
                    skipped += 1
                    continue

                digest = hashlib.sha256(script_text.encode("utf-8")).hexdigest()
                existing = self._get_existing_digest(script_name)
                if existing:
                    if existing != digest:
                        raise CommandError(
                            "DB apply SQL: el script ya fue aplicado con otro hash. "
                            f"script={script_name} hash_actual={digest} hash_registrado={existing}"
                        )
                    skipped += 1
                    continue

                self.stdout.write(f"DB apply SQL: aplicando {script_name}...")
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(script_text)
                        cursor.execute(
                            f"""
                            INSERT INTO {PATCHES_TABLE}(script_name, sha256)
                            VALUES (%s, %s)
                            """,
                            [script_name, digest],
                        )
                applied += 1
                self.stdout.write(self.style.SUCCESS(f"DB apply SQL: OK {script_name}"))

            self.stdout.write(
                self.style.SUCCESS(
                    f"DB apply SQL: completado. aplicados={applied} omitidos={skipped} total={len(scripts)}"
                )
            )
        finally:
            self._release_lock()

    def _enabled(self) -> bool:
        raw = (os.getenv(PATCHES_ENABLED_ENV, "1") or "").strip().lower()
        return raw not in ("0", "false", "no", "off")

    def _resolve_patches_dir(self, cli_value: str) -> Path:
        if cli_value.strip():
            return Path(cli_value).expanduser().resolve()
        env_value = (os.getenv(PATCHES_DIR_ENV, "") or "").strip()
        if env_value:
            return Path(env_value).expanduser().resolve()
        candidates = [
            (Path(settings.BASE_DIR).resolve() / "sql" / "applies"),
            (Path(settings.BASE_DIR).resolve().parent / "sql" / "applies"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return candidates[0].resolve()

    def _read_script(self, script_path: Path) -> str:
        data = script_path.read_text(encoding="utf-8")
        return data.lstrip("\ufeff")

    def _acquire_lock(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [ADVISORY_LOCK_KEY])

    def _release_lock(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])

    def _ensure_registry_table(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {PATCHES_TABLE} (
                  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                  script_name TEXT NOT NULL UNIQUE,
                  sha256 TEXT NOT NULL,
                  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

    def _get_existing_digest(self, script_name: str) -> str:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT sha256
                FROM {PATCHES_TABLE}
                WHERE script_name = %s
                """,
                [script_name],
            )
            row = cursor.fetchone()
        return (row[0] if row else "") or ""
