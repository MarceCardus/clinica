-- Migración: índices de rendimiento
-- Fecha: 2026-08-19
--
-- En PostgreSQL las FOREIGN KEYS **no** se indexan automáticamente (solo las
-- PK y los UNIQUE). Estos índices cubren columnas que la app filtra, ordena o
-- usa en JOINs sobre tablas que crecen con el uso. Sin ellos, esas consultas
-- hacen scan secuencial de toda la tabla y saturan la red hacia el servidor.
--
-- Cada índice va CONCURRENTLY (no bloquea escrituras) + IF NOT EXISTS
-- (idempotente). CONCURRENTLY NO puede correr dentro de una transacción,
-- por eso este archivo NO lleva BEGIN/COMMIT. Si algún CREATE se interrumpe,
-- puede quedar un índice INVALID: borralo con DROP INDEX y volvé a correrlo.
--
-- Verificar después con:
--   EXPLAIN ANALYZE <consulta>;    -- debe decir "Index Scan", no "Seq Scan"


-- =====================================================================
-- TIER 1 — ALTO IMPACTO (informes de ventas/cobros, historial de paciente)
-- =====================================================================

-- historial.py / ficha: total ventas y saldo por paciente en cada apertura.
-- También JOIN en cobro_dialog, informe_ventas, buscar_venta.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_venta_idpaciente
    ON venta (idpaciente);

-- informe_ventas: filtro por rango de fecha + ORDER BY fecha en cada informe.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_venta_fecha
    ON venta (fecha);

-- JOIN venta_detalle -> venta en TODOS los informes de ventas y en la ficha.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_venta_detalle_idventa
    ON venta_detalle (idventa);

-- JOIN venta_detalle -> item (informe de ventas por item).
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_venta_detalle_iditem
    ON venta_detalle (iditem);

-- anular_cobro / historial: cobros por paciente.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cobro_idpaciente
    ON cobro (idpaciente);

-- cobro_venta: idventa es la 2da columna del PK (idcobro, idventa), por lo que
-- NO tiene índice propio. Buscar los cobros de una venta lo necesita.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cobro_venta_idventa
    ON cobro_venta (idventa);

-- stock_movimiento: ficha clínica consulta/consume stock por item. Tabla que
-- crece mucho (un movimiento por cada consumo/ingreso).
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_stock_movimiento_iditem
    ON stock_movimiento (iditem);

-- stock_movimiento: reversa de procedimiento -> filter_by(motivo, idorigen).
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_stock_movimiento_motivo_idorigen
    ON stock_movimiento (motivo, idorigen);


-- =====================================================================
-- TIER 2 — MEDIO (se abre por cada paciente / validaciones de agenda)
-- =====================================================================

-- ficha clínica: indicaciones (recetas) del paciente.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_indicacion_idpaciente
    ON indicacion (idpaciente);

-- ficha clínica: recordatorios del paciente.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_recordatorio_paciente_idpaciente
    ON recordatorio_paciente (idpaciente);

-- ficha clínica: procedimientos del paciente.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_procedimiento_idpaciente
    ON procedimiento (idpaciente);

-- fotos de avance por paciente.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_fotoavance_idpaciente
    ON fotoavance (idpaciente);

-- abm_turnos: estadísticas de frecuencia/duración por profesional.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cita_idprofesional
    ON cita (idprofesional);

-- informe_compras: filtro/orden por fecha (idproveedor ya está indexado).
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_compra_fecha
    ON compra (fecha);


-- =====================================================================
-- TIER 3 — OPCIONAL (por paciente; tablas más chicas, ganancia menor)
-- Descomentá si notás lentitud al abrir la ficha con muchos pacientes.
-- =====================================================================

-- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_antec_familiar_idpaciente
--     ON antecedente_familiar (idpaciente);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_antec_patologico_idpaciente
--     ON antecedente_patologico_personal (idpaciente);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_antec_enf_actual_idpaciente
--     ON antecedente_enfermedad_actual (idpaciente);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_caja_chica_mov_idcajachica
--     ON caja_chica_movimiento (idcajachica);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_plan_sesion_idplan
--     ON plan_sesion (idplan);
