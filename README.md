# Plataforma de apuestas internas (MVP)

Este repositorio contiene un MVP completo para gestionar apuestas con saldo virtual en torneos internos de fútbol entre empresas. Incluye backend en FastAPI, backoffice web en React + Vite y aplicación móvil en Expo/React Native. Toda la infraestructura local se orquesta con Docker Compose y emplea SQL Server y MinIO.

## Características principales

- **Roles:** administrador, organizador y usuario final con autenticación JWT (access + refresh).
- **KYC básico:** almacenamiento de documento y verificación de mayoría de edad.
- **Ledger de saldo virtual:** recargas, apuestas, premios y retiros con hash y bitácora de auditoría.
- **Mercados soportados:** 1X2 y Over/Under con cierre automático 10 minutos antes del partido.
- **Torneos internos:** CRUD de torneos, equipos, partidos, mercados y cuotas.
- **Backoffice web:** aprobación de recargas/retiros, gestión de cuotas y cierre de mercados, auditoría.
- **App móvil (Expo):** registro/login, recargas con comprobante, consulta de saldo, apuestas y retiros.
- **Seguridad:** rate limiting, CORS seguro, logs estructurados y request-id, hashes SHA-256 para archivos/comprobantes.

## Estructura del proyecto

```
backend/     # FastAPI + SQLAlchemy + Alembic + Pytest
admin/       # Backoffice React + Vite + TypeScript + Zustand
mobile/      # Aplicación Expo / React Native + React Navigation
Dockerfile   # Dockerfiles de cada servicio
README.md    # Este documento
```

## Requisitos

- Docker Desktop o Docker Engine + Docker Compose v2
- (Opcional) Python 3.11 + Poetry para ejecutar backend sin contenedores
- (Opcional) Node 18+ para ejecutar las aplicaciones front fuera de Docker

## Puesta en marcha rápida (Docker)

```bash
docker compose up -d --build
```

Servicios expuestos:

| Servicio | URL | Descripción |
| --- | --- | --- |
| API | http://localhost:8000 | FastAPI + documentación interactiva en `/docs` |
| Admin | http://localhost:5173 | Backoffice React (usar credenciales seed) |
| Mobile (Expo) | http://localhost:19000 | Dev server Expo (escanea QR con Expo Go) |
| SQL Server | localhost:1433 | Motor de base de datos (usuario `sa`) |
| MinIO Console | http://localhost:9001 | Consola de storage (user/pass `betapp/betappsecret`) |

La configuración por defecto se define en `backend/.env.example`, `admin/.env.example` y `mobile/.env.example`. Puedes copiarlos a `.env` y ajustar según tus necesidades.

## Migraciones y datos de ejemplo

```bash
# Ingresar al contenedor API
docker compose exec api bash

# Aplicar migraciones
poetry run alembic upgrade head

# Cargar seed (admin + torneo de muestra)
poetry run python -m app.seed.seed_data
```

El seed crea:

- Usuario administrador: `admin@example.com` / `ChangeMe123!`
- Torneo «Liga Interna» con 4 equipos, 3 partidos y mercados con cuotas precargadas.

## Flujo end-to-end sugerido

1. Registrar un usuario final vía aplicación móvil o POST `/auth/register`.
2. El usuario solicita recarga subiendo comprobante (`POST /wallet/topups`).
3. El administrador ingresa al backoffice (`admin/`) y aprueba la recarga.
4. El usuario consulta saldo y realiza una apuesta (`POST /bets`).
5. El administrador carga el resultado del partido (`PATCH /tournaments/matches/{id}/result`) y se liquidan las apuestas.
6. El usuario solicita retiro (`POST /wallet/withdrawals`), el admin lo marca como pagado y se genera el asiento.

Todo movimiento relevante queda registrado en `audit_log` con hash y request-id.

## Scripts útiles

### Backend (desde `backend/`)

```bash
make install      # Instala dependencias con Poetry
make dev          # Levanta uvicorn con autoreload
make migrate      # Ejecuta Alembic upgrade head
make seed         # Ejecuta seed de datos
make test         # Corre Pytest
```

### Frontend Admin (desde `admin/`)

```bash
npm install
npm run dev
npm run build
```

### App móvil (desde `mobile/`)

```bash
npm install
npx expo start
```

## Testing

La suite incluye pruebas de integración mínimas con Pytest que cubren:

- Registro y login (`/auth/register`, `/auth/login`).
- Flujo de recarga aprobada por admin (`/wallet/topups`).
- Colocación y liquidación de apuesta (`/bets`, `/tournaments/matches/{id}/result`).

Ejecuta las pruebas desde `backend/`:

```bash
poetry run pytest
```

## Consideraciones de cumplimiento

- El formulario de registro exige fecha de nacimiento >= 18 años.
- Cada comprobante de recarga se valida contra hash SHA-256 para evitar duplicados.
- Se aplican límites diarios configurables (`MAX_DAILY_TOPUP`, `MAX_DAILY_STAKE`).
- Los mercados se bloquean automáticamente 10 minutos antes del inicio y al pasar a estado LIVE.
- Todas las operaciones financieras generan registros en `wallet_ledger` y `audit_log` con hash.
- Stub `/wallet/bank/webhook` listo para integración con bancos en el futuro.

## Estructura de base de datos

Las migraciones Alembic crean las tablas especificadas en el requerimiento (users, kyc, wallet_ledger, topups, withdrawals, tournaments, teams, matches, markets, odds, bets, audit_log) con índices clave para performance y trazabilidad.

## Soporte adicional

- **Logs estructurados:** se generan en JSON con `structlog`, incluyendo request-id para correlación.
- **Rate limiting:** implementado vía `slowapi` (valor configurable con `RATE_LIMIT`).
- **MinIO fallback:** si no hay conexión a MinIO, los archivos se guardan temporalmente en `/tmp/proofs`.

## Próximos pasos sugeridos

- Integración con proveedor de KYC en producción.
- Implementación de WebSockets para cuotas en tiempo real.
- Automatización CI/CD en GitHub Actions utilizando los scripts `make` y `npm` provistos.

---

Para cualquier duda o mejora, revisa los módulos correspondientes en `backend/app`, `admin/src` y `mobile/src`.
