#!/usr/bin/env python
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import psycopg2


CODE_RE = re.compile(r"^\s*(\d{5,10})\s+")
PRICE_RE = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
HS_RE = re.compile(r"\d{4}\.\d{2}\.\d{2}")


def load_env_file(path: Path) -> None:
    if not path or not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def pdf_to_lines(pdf_path: Path) -> list[str]:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        raise RuntimeError("pdftotext not found on PATH")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            [pdftotext, "-layout", str(pdf_path), str(tmp_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return tmp_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _is_continuation(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("."):
        return False
    if s.startswith("="):
        return False
    if "MAGNAMED CONFIDENTIAL" in s:
        return False
    if s.startswith("Price List") or s.startswith("PRODUCTS") or s.startswith("Item Code"):
        return False
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return False
    return True


def _join_pieces(pieces: list[str]) -> str:
    out = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if out.endswith("-"):
            out = out[:-1] + piece.lstrip()
        elif out:
            out += " " + piece
        else:
            out = piece
    return " ".join(out.split())


def parse_items(lines: list[str]) -> tuple[dict[str, Decimal], dict[str, str], list[tuple], int]:
    entries = []
    for idx, line in enumerate(lines):
        m = CODE_RE.match(line)
        if not m:
            continue
        code = m.group(1).strip()
        rest = line[m.end():]
        hs = HS_RE.search(rest)
        cut = hs.start() if hs else len(rest)
        segment = rest[:cut]
        pm = PRICE_RE.search(segment)
        if not pm:
            continue
        price = Decimal(pm.group(0).replace(",", ""))
        desc = segment[:pm.start()].rstrip()
        entries.append((idx, code, desc, price))

    prefix: dict[int, list[str]] = {}
    suffix: dict[int, list[str]] = {}
    for i, entry in enumerate(entries):
        idx = entry[0]
        next_idx = entries[i + 1][0] if i + 1 < len(entries) else len(lines)
        between = [lines[k] for k in range(idx + 1, next_idx) if _is_continuation(lines[k])]
        if between:
            if i + 1 < len(entries) and not entries[i + 1][2].strip():
                prefix.setdefault(i + 1, []).extend(between)
            else:
                suffix.setdefault(i, []).extend(between)

    items: dict[str, Decimal] = {}
    names: dict[str, str] = {}
    conflicts: list[tuple] = []
    duplicates = 0
    for i, entry in enumerate(entries):
        _, code, desc, price = entry
        prev = items.get(code)
        if prev is not None:
            if prev != price:
                conflicts.append((code, prev, price, entry[0] + 1))
            else:
                duplicates += 1
            continue
        items[code] = price

        parts: list[str] = []
        if i in prefix:
            parts.extend(prefix[i])
        if desc:
            parts.append(desc)
        if i in suffix:
            parts.extend(suffix[i])
        full_desc = _join_pieces(parts)
        if full_desc:
            cur = names.get(code, "")
            if len(full_desc) > len(cur):
                names[code] = full_desc

    return items, names, conflicts, duplicates


def connect_db(host_override: str | None = None):
    host = host_override or os.getenv("POSTGRES_HOST", "localhost")
    if host == "postgres":
        host = "localhost"
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=host,
        port=os.getenv("POSTGRES_PORT", "5432"),
    )


def apply_updates(
    conn,
    items: dict[str, Decimal],
    names: dict[str, str],
    apply: bool,
    insert_missing: bool,
) -> tuple[int, int, list[str]]:
    if not items:
        return 0, 0, []
    codes = list(items.keys())
    upper_codes = [c.upper() for c in codes]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT UPPER(codigo) FROM catalogo_repuestos WHERE UPPER(codigo)=ANY(%s)",
            [upper_codes],
        )
        existing = {row[0] for row in (cur.fetchall() or [])}
        missing = [c for c in codes if c.upper() not in existing]
        rows = [(items[c], c) for c in codes if c.upper() in existing]
        if apply and rows:
            cur.executemany(
                """
                UPDATE catalogo_repuestos
                   SET costo_usd=%s, updated_at=NOW()
                 WHERE UPPER(codigo)=UPPER(%s)
                """,
                rows,
            )
        inserted = 0
        if apply and insert_missing and missing:
            insert_rows = []
            for code in missing:
                name = names.get(code) or f"MAGNAMED {code}"
                insert_rows.append((code, name, items[code]))
            cur.executemany(
                """
                INSERT INTO catalogo_repuestos (codigo, nombre, costo_usd, activo, marca_fabricante, updated_at)
                VALUES (%s,%s,%s,TRUE,'Magnamed',NOW())
                """,
                insert_rows,
            )
            inserted = len(insert_rows)
        if apply:
            conn.commit()
        else:
            conn.rollback()
        return len(rows), inserted, missing


def write_csv(path: Path, items: dict[str, Decimal], names: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["codigo", "nombre", "costo_usd"])
        for code in sorted(items.keys()):
            w.writerow([code, names.get(code, ""), f"{items[code]:.2f}"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Magnamed price list PDF into catalogo_repuestos.costo_usd")
    parser.add_argument("--pdf", required=True, help="Path to Magnamed price list PDF")
    parser.add_argument("--env", default=".env.prod", help="Path to .env file (default: .env.prod)")
    parser.add_argument("--host", default=None, help="Override DB host (default: from env)")
    parser.add_argument("--csv", default=None, help="Optional output CSV path")
    parser.add_argument("--apply", action="store_true", help="Apply updates to DB (default: dry-run)")
    parser.add_argument(
        "--insert-missing",
        action="store_true",
        help="Insert missing codes into catalogo_repuestos",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    env_path = Path(args.env) if args.env else None
    if env_path:
        load_env_file(env_path)

    lines = pdf_to_lines(pdf_path)
    items, names, conflicts, duplicates = parse_items(lines)

    if args.csv:
        write_csv(Path(args.csv), items, names)

    if conflicts:
        print(f"Conflicts: {len(conflicts)} (first 5 shown)")
        for code, prev, new, idx in conflicts[:5]:
            print(f"- code={code} prev={prev} new={new} line={idx}")

    try:
        conn = connect_db(args.host)
    except Exception as e:
        print(f"DB connection failed: {e}", file=sys.stderr)
        return 2

    try:
        updated, inserted, missing = apply_updates(conn, items, names, apply=args.apply, insert_missing=args.insert_missing)
    finally:
        conn.close()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"{mode} parsed_items={len(items)} duplicates={duplicates} updated={updated} inserted={inserted} missing={len(missing)}"
    )
    if missing:
        print("Missing codes (first 20):")
        for code in missing[:20]:
            print(f"- {code}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
