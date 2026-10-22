# Arquitectura — PickMaster

## Vista general

```
Fuentes (API/CSV)
      │
      ▼
 worker (ingesta + features + modelos)
      │
      ├── PostgreSQL
      ├── Redis
      └── API FastAPI
              │
              ▼
       Dashboard SvelteKit
```

## Componentes

| Componente | Responsabilidad |
|---|---|
| `worker` | Ingesta, features, entrenamiento y picks |
| `api` | Consultas, administración y salud |
| `web` | Dashboard |
| `postgres` | Datos históricos, proyecciones y picks |
| `redis` | Colas, caché y locks |

## Flujo

1. Descargar fixtures, equipos, jugadores y estadísticas.
2. Normalizar y guardar en PostgreSQL.
3. Construir features por jugador/partido.
4. Entrenar o cargar el modelo.
5. Simular puntos y generar picks.
6. Publicar en API y dashboard.
7. Guardar resultados reales y evaluar.

## Jobs

- **Diario:** fixtures y estadísticas.
- **Cada 6 h:** noticias, lesiones y probables alineaciones.
- **T-24h:** picks preliminares.
- **T-6h:** actualización.
- **T-1h:** alineaciones confirmadas y picks finales.
- **Post-partido:** estadísticas finales, evaluación de picks, reporte y
  notificación (dashboard/Telegram/email).

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/health` | Salud |
| `GET` | `/api/matches` | Jornada |
| `GET` | `/api/matches/{id}` | Detalle |
| `GET` | `/api/picks?match_id=` | Picks |
| `GET` | `/api/players/{id}/projection` | Proyección |
| `GET` | `/api/backtest` | Métricas |
| `GET` | `/api/results?match_id=` | Resultados de picks |
| `GET` | `/api/results/summary` | Hit rate acumulado |
| `POST` | `/api/admin/evaluate?match_id=` | Evaluar partido |
| `POST` | `/api/admin/refresh` | Refrescar |

## Base de datos

- `teams`, `players`, `matches`.
- `player_stats`, `lineups`, `injuries`.
- `projections`, `picks`, `pick_results`, `match_reports`.
- `model_runs`, `contest_rules`, `audit_log`.

## Despliegue

- `/opt/apps/PickMaster` en el HomeLab.
- `docker compose up -d`.
- Caddy en `127.0.0.1:8087`.
- API y worker en la red interna.
- Cloudflare Tunnel para el dominio.
- Backups de PostgreSQL y modelos.

## Seguridad

- Sin scraping de Draftea.
- Sin credenciales de Draftea en el servidor.
- Reglas y salarios cargados manualmente.
- Datos de API con keys en `.env`.
- Sin secretos en logs.
