# PickMaster

Asistente de **picks probabilísticos para Draftea · Liga MX**. Antes de cada
partido entrega los jugadores con mayor probabilidad y puntos esperados, con
nivel de confianza y explicación.

> Proyecto personal de análisis. No garantiza resultados, no automatiza apuestas
> y no sustituye las reglas de Draftea. Solo para mayores de edad.

## Qué hace

- Ingesta de partidos, jugadores, estadísticas, lesiones y alineaciones.
- Proyección de minutos y puntos fantasy por jugador.
- Simulación Monte Carlo para rangos y probabilidades.
- Picks por partido y por posición.
- Dashboard con probabilidad, puntos esperados, confianza y motivo.
- Backtesting con torneos anteriores.
- Actualización antes del partido: T-24h, T-6h y T-1h (alineaciones).
- **Evaluación post-partido:** te dice qué picks acertaron ✅, cuáles quedaron
  parciales 🟡, cuáles fallaron ❌ y quiénes no jugaron ⚪.
- Notificación opcional por dashboard, Telegram o email.

## Stack

| Capa | Tecnología |
|---|---|
| Datos / modelos | Python 3.12 · pandas · scikit-learn · XGBoost/LightGBM |
| API | FastAPI · SQLAlchemy · Alembic |
| BD | PostgreSQL existente |
| Jobs | APScheduler o Celery + Redis |
| Dashboard | SvelteKit 3 + TypeScript + Tailwind v4 |
| Web | Docker · Caddy · Cloudflare Tunnel |

## Puertos y dominio

- Web: `127.0.0.1:8087`
- API: `api:8000` (solo red interna)
- Dominio: `pickmaster.hapmed.qzz.io`
- Repo: `hapmed/PickMaster`
- Base: `pickmaster` en el PostgreSQL existente

## Documentación

- [`AGENTS.md`](./AGENTS.md) — brief completo para el agente.
- [`ACCESOS.md`](./ACCESOS.md) — servidor, BD, GitHub, Cloudflare, R2 y SMB.
- [`docs/ARQUITECTURA.md`](./docs/ARQUITECTURA.md) — pipeline, API y datos.
- [`docs/MODELO.md`](./docs/MODELO.md) — features, modelos, calibración y backtest.
- [`docs/FUENTES_DATOS.md`](./docs/FUENTES_DATOS.md) — fuentes legales y límites.
- [`config/contest_rules.example.json`](./config/contest_rules.example.json) — reglas a completar.

## Estado

**Fase 1 implementada** (Fase 2/3/4 pendientes).

| Bloque | Estado |
|---|---|
| Backend FastAPI + SQLAlchemy (todas las rutas de la tabla API) | ✅ verificadas en tests |
| Motor de proyección: minutos + eventos + Monte Carlo 10k | ✅ determinista por `partido/jugador` |
| Picks por posición con probabilidad, target, confianza y motivo | ✅ |
| Evaluación post-partido ✅🟡❌⚪ + hit rate + reporte | ✅ |
| Ingesta manual por CSV (únicos datos permitidos) | ✅ CSV en `data/` |
| Semilla demo determinista (solo para desarrollo) | ✅ |
| Lint/mypy/pytest | ✅ `ruff`, `mypy app` y 20 tests pasando |
| `docker compose config` | ⚠️ YAML validado con parser; Docker no disponible en contenedor dev |
| Dashboard SvelteKit | ⬜ Fase 2 |
| Jobs T-24h/T-6h/T-1h y notificación | ⬜ Fase 3 |

Reglas de Draftea **aún pendientes de cargar**: mientras no exista
`backend/config/contest_rules.json` con valores reales, el motor usa pesos
PROVISIONALES (documentados en `app/rules.py`) y así lo marca `/api/health`.
Salarios: vía `data/salaries.csv` o `data/players.csv`.

### Cómo correr (local)

```bash
cp backend/.env.example backend/.env   # ajusta PICKMASTER_DATABASE_URL
cd backend && uv sync
uv run python -m app.worker.cli seed-demo          # datos demo
uv run python -m app.worker.cli generate-picks --match 7
uv run python -m app.worker.cli evaluate --match 7
uv run python -m app.worker.cli report --match 7
uv run uvicorn app.main:app --port 8000            # API
```

Pendiente de definir: fuente de datos y reglas exactas del concurso de Draftea.
