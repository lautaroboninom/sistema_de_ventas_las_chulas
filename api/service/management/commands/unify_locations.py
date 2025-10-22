from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = (
        "Unifica ubicaciones duplicadas hacia un nombre canónico y re-asigna ingresos. "
        "Por defecto normaliza a 'Estantería de Alquiler'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--target",
            default="Estantería de Alquiler",
            help="Nombre canónico de destino.",
        )
        parser.add_argument(
            "--alias",
            action="append",
            default=[],
            help=(
                "Alias adicionales a unificar (puede repetirse). "
                "Si no se especifican, se usan alias comunes para 'Estantería de Alquiler'."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra lo que haría sin aplicar cambios.",
        )

    def handle(self, *args, **opts):
        target_name = (opts.get("target") or "").strip()
        if not target_name:
            self.stderr.write("--target no puede ser vacío")
            return 1

        dry = bool(opts.get("dry_run"))
        aliases = [
            a.strip() for a in (opts.get("alias") or []) if (a or "").strip()
        ]

        # Defaults for the common case requested
        if not aliases and target_name.lower() == "estantería de alquiler":
            aliases = [
                "Estantería alquiler",
                "Estanteria alquiler",
                "Estanteria de Alquiler",
                "Estantería de Aluiler",  # typos frecuentes
                "Estanteria de Aluiler",
                "Estanteria alquileres",
            ]

        # Normalize compare values
        def _lowers(items):
            out = []
            for it in items:
                it = (it or "").strip()
                if it:
                    out.append(it.lower())
            return list(dict.fromkeys(out))

        low_aliases = _lowers(aliases)
        low_target = target_name.lower()

        if low_target in low_aliases:
            low_aliases = [x for x in low_aliases if x != low_target]

        self.stdout.write(
            f"Objetivo: '{target_name}' | Aliases: {', '.join(low_aliases) if low_aliases else '(ninguno)'}"
        )

        def _norm(txt: str) -> str:
            try:
                import unicodedata
                s = (txt or "").strip().lower()
                s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
                return " ".join(s.split())
            except Exception:
                return (txt or "").strip().lower()

        with transaction.atomic():
            with connection.cursor() as cur:
                # 1) Obtener/crear ubicación canónica
                cur.execute(
                    "SELECT id, nombre FROM locations WHERE LOWER(nombre)=LOWER(%s) LIMIT 1",
                    [target_name],
                )
                row = cur.fetchone()
                target_id = row[0] if row else None
                # Fallback: comparar con normalización (sin acentos)
                if not target_id:
                    try:
                        cur.execute("SELECT id, nombre FROM locations")
                        rows = cur.fetchall() or []
                        target_norm = _norm(target_name)
                        for rid, rname in rows:
                            if _norm(rname) == target_norm:
                                target_id = rid
                                break
                    except Exception:
                        pass

                # Si no existe, intentar renombrar algún alias a canónico, o crearla
                if not target_id:
                    target_exists = False
                    # Buscar primera fila con algún alias exacto (lower)
                    if low_aliases:
                        # Construir cláusula dinámica
                        where = " OR ".join(["LOWER(nombre)=%s"] * len(low_aliases))
                        cur.execute(
                            f"SELECT id, nombre FROM locations WHERE {where} ORDER BY id LIMIT 1",
                            low_aliases,
                        )
                        alias_row = cur.fetchone()
                    else:
                        alias_row = None

                    if alias_row:
                        alias_id = alias_row[0]
                        # Renombrar alias a destino si no existe otro con destino
                        cur.execute(
                            "SELECT id FROM locations WHERE LOWER(nombre)=LOWER(%s) LIMIT 1",
                            [target_name],
                        )
                        exists2 = cur.fetchone()
                        if not exists2 and not dry:
                            cur.execute(
                                "UPDATE locations SET nombre=%s WHERE id=%s",
                                [target_name, alias_id],
                            )
                            target_id = alias_id
                        else:
                            target_id = exists2[0] if exists2 else alias_id
                            target_exists = bool(exists2)
                    else:
                        if dry:
                            self.stdout.write("DRY-RUN: crearía ubicación canónica")
                            # Simular id
                            target_id = -1
                        else:
                            cur.execute(
                                "INSERT INTO locations(nombre) VALUES (%s) RETURNING id",
                                [target_name],
                            )
                            target_id = cur.fetchone()[0]

                # 2) Reasignar ingresos que apunten a alias al id canónico
                moved_count = 0
                deleted_count = 0
                alias_ids = []
                if low_aliases:
                    where = " OR ".join(["LOWER(nombre)=%s"] * len(low_aliases))
                    cur.execute(
                        f"SELECT id, nombre FROM locations WHERE {where}",
                        low_aliases,
                    )
                    alias_ids = [r[0] for r in cur.fetchall() or []]
                # También considerar coincidencias por normalización para aliases
                try:
                    cur.execute("SELECT id, nombre FROM locations")
                    rows_all = cur.fetchall() or []
                    alias_norms = set(_lowers(aliases))
                    alias_norms.add(_norm(target_name))
                    for rid, rname in rows_all:
                        if _norm(rname) in alias_norms and rid not in alias_ids and rid != target_id:
                            alias_ids.append(rid)
                except Exception:
                    pass

                # Incluir variantes que sean casi iguales al destino (sin acentos)
                # ya cubiertas por low_aliases; no añadimos heurística extra para evitar falsos positivos.

                for aid in alias_ids:
                    if aid == target_id:
                        continue
                    # Mover ingresos
                    cur.execute(
                        "SELECT COUNT(*) FROM ingresos WHERE ubicacion_id=%s",
                        [aid],
                    )
                    c = int(cur.fetchone()[0] or 0)
                    if c and not dry:
                        cur.execute(
                            "UPDATE ingresos SET ubicacion_id=%s WHERE ubicacion_id=%s",
                            [target_id, aid],
                        )
                    moved_count += c
                    # Borrar ubicación duplicada
                    if not dry:
                        cur.execute("DELETE FROM locations WHERE id=%s", [aid])
                    deleted_count += 1

                # 3) Consolidar: asegurar única fila canónica (si por carrera existe otra)
                # Si hubiera quedado otra fila exactamente igual por condiciones de carrera, no la tocamos aquí.

                self.stdout.write(
                    (
                        f"OK: target_id={target_id} | ingresos_actualizados={moved_count} | "
                        f"ubicaciones_eliminadas={deleted_count}"
                    )
                )

        return 0
