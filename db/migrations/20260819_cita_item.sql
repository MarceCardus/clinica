-- Migración: múltiples zonas (items) por turno
-- Fecha: 2026-08-19
--
-- Crea la tabla puente cita_item (un turno -> varias zonas del catálogo de items).
-- NO se modifica cita.iditem ni su CheckConstraint: esa columna sigue siendo la
-- "zona principal" que usa el enlazado de planes (agenda_plan_linker) y las
-- estadísticas de frecuencia/duración.
--
-- IMPORTANTE: hacer un backup del schema antes de correr esto.
--   pg_dump ... > backups/consultorio_pre_cita_item.sql

BEGIN;

CREATE TABLE IF NOT EXISTS cita_item (
    idcita  INTEGER NOT NULL REFERENCES cita(idcita) ON DELETE CASCADE,
    iditem  INTEGER NOT NULL REFERENCES item(iditem),
    PRIMARY KEY (idcita, iditem)
);

CREATE INDEX IF NOT EXISTS ix_cita_item_iditem ON cita_item(iditem);

-- Backfill: llevar la zona actual de cada turno a la tabla nueva.
INSERT INTO cita_item (idcita, iditem)
SELECT idcita, iditem
FROM cita
WHERE iditem IS NOT NULL
ON CONFLICT DO NOTHING;

COMMIT;
