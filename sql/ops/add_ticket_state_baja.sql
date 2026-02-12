-- Agrega el estado "baja" al enum ticket_state sin fallar si ya existe.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM pg_enum e
      JOIN pg_type t ON t.oid = e.enumtypid
     WHERE t.typname = 'ticket_state'
       AND e.enumlabel = 'baja'
  ) THEN
    ALTER TYPE ticket_state ADD VALUE 'baja' AFTER 'entregado';
  END IF;
END $$;
