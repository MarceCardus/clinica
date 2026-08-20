-- Migración: índice sobre cita.fecha_inicio
-- Fecha: 2026-08-19
--
-- La agenda (day/week view) filtra las citas por rango de fecha
-- (controllers/abm_turnos.py -> _cargar_citas). Sin este índice, cada
-- navegación de día/semana hace un scan secuencial de toda la tabla cita,
-- que crece con el histórico y satura la red hacia el servidor de BD.
--
-- CREATE INDEX CONCURRENTLY no puede correr dentro de una transacción,
-- por eso NO se usa BEGIN/COMMIT aquí. Se usa CONCURRENTLY para no
-- bloquear escrituras sobre la tabla cita mientras se crea el índice.

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cita_fecha_inicio
    ON cita (fecha_inicio);
