import os
import psycopg2


def load_env(path):
    env = {}
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def main():
    env = load_env(os.path.join(os.getcwd(), '.env.prod'))
    host = env.get('POSTGRES_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
    port = int(env.get('POSTGRES_PORT', os.getenv('POSTGRES_PORT', '5432')))
    db = env.get('POSTGRES_DB', os.getenv('POSTGRES_DB', 'servicio_tecnico'))
    user = env.get('POSTGRES_USER', os.getenv('POSTGRES_USER', 'sepid'))
    pw = env.get('POSTGRES_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))

    sql = (
        """
CREATE TABLE IF NOT EXISTS ingreso_alquiler_accesorios (
  id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingreso_id    INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  accesorio_id  INTEGER NOT NULL REFERENCES catalogo_accesorios(id) ON DELETE RESTRICT,
  referencia    TEXT NULL,
  descripcion   TEXT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ingreso_alq_acc_ingreso ON ingreso_alquiler_accesorios(ingreso_id);
CREATE INDEX IF NOT EXISTS idx_ingreso_alq_acc_accesorio ON ingreso_alquiler_accesorios(accesorio_id);
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_ingreso_alquiler_accesorios') THEN
    CREATE TRIGGER trg_audit_ingreso_alquiler_accesorios
    AFTER INSERT OR UPDATE OR DELETE ON ingreso_alquiler_accesorios
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
END $$;
        """
    )

    conn = None
    last_err = None
    for h in (host, '127.0.0.1', 'localhost'):
        try:
            conn = psycopg2.connect(host=h, port=port, dbname=db, user=user, password=pw)
            host = h
            break
        except Exception as e:
            last_err = e
            conn = None

    if conn is None:
        raise SystemExit(f"No se pudo conectar a PostgreSQL: {last_err}")

    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql)
        print(f"DDL aplicada OK en {host}:{port}/{db}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

