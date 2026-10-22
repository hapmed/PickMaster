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

- Web: `127.0.0.1:8087` (host → contenedor web)
- API: `127.0.0.1:8088` (host → contenedor api)
- Dominio: `pickmaster.hapmed.qzz.io` (túnel Cloudflare `HomeLabServer`):
  - `/` → dashboard SvelteKit, `/api/*` → API FastAPI (regla por `path` en ingress)
- Repo: `hapmed/PickMaster`
- Base: `pickmaster` en el PostgreSQL existente (usuario `pickmaster_app`)
- Servidor: `/opt/apps/PickMaster` (compose + `.env` con credenciales; el `.env`
  vive solo en el servidor, nunca en git)

## Documentación

- [`AGENTS.md`](./AGENTS.md) — brief completo para el agente.
- [`ACCESOS.md`](./ACCESOS.md) — servidor, BD, GitHub, Cloudflare, R2 y SMB.
- [`docs/ARQUITECTURA.md`](./docs/ARQUITECTURA.md) — pipeline, API y datos.
- [`docs/MODELO.md`](./docs/MODELO.md) — features, modelos, calibración y backtest.
- [`docs/FUENTES_DATOS.md`](./docs/FUENTES_DATOS.md) — fuentes legales y límites.
- [`config/contest_rules.example.json`](./config/contest_rules.example.json) — reglas a completar.

## Estado

**Fases 1–4 implementadas** (Fase 4: backtest real con datos ESPN).

| Bloque | Estado |
|---|---|
| Backend FastAPI + SQLAlchemy (todas las rutas de la tabla API) | ✅ |
| Motor de proyección: minutos + eventos + Monte Carlo 10k | ✅ determinista |
| Picks por posición + **SELECCIÓN 5 ESTRELLAS** (probabilidad × puntos × confianza, con sección "¿Por qué?") | ✅ `/api/picks/top` |
| Evaluación post-partido ✅🟡❌⚪ + hit rate + reporte — **con stats reales ESPN ya ingesta automática** | ✅ |
| Ingesta manual por CSV (reglas, salarios, XI confirmado) | ✅ |
| **Ingesta ESPN** (fixtures 95 partidos, 3147 stats por jugador, rosters completos 611 jugadores, alineaciones confirmadas post-partido; llamada respetuosa 3s/UA) | ✅ `app/ingestion/espn.py` |
| Ingesta online TheSportsDB (equipos/jugadores/calendario, key pública `123`, acumulativa y respetando 429) | ✅ reservada a rosters restantes |
| Alineaciones/convocatorias estimadas del roster (`/api/lineups`) | ✅ |
| Dashboard SvelteKit con estética Apple HIG: insignias de camiseta por jugador (determinista), selector de partidos, filas de picks por posición, alineaciones en chips, claro/oscuro automáticos, contraste AA | ✅ check+test+build OK |
| Scheduler Fase 3 (T-24h / T-6h / T-1h + evaluación post-partido con ledger `worker_jobs`) — T-24h trae agenda ESPN, post-partido trae stats ESPN antes de evaluar | ✅ testado; activo con `PICKMASTER_ESPN_SCHEDULE=1` |
| Notificación Telegram/email (interesados: env por claves) | ✅ módulo listo; sin credencial es irrelevante en dashboard |
| Lint/mypy/pytest backend | ✅ 34 tests · ruff · mypy strict |
| Dashboard checks | ✅ svelte-check 0 errors · vitest · vite build |
| Despliegue HomeLab (compose `pickmaster_*` en apps-net, BD Postgres `pickmaster`, túnel Cloudflare con regla aditiva) | ✅ vivo en `pickmaster.hapmed.qzz.io` |
| **Backtest Fase 4** (corte anti-fuga, MAE por posición, baseline, calibración percentilística, Brier por umbral, titularidad) sobre 587 rows reales | ✅ `/api/backtest` · CLI `backtest` |
| Backtest con torneos anteriores | ⬜ bloqueado por falta de datos históricos por jugador |

### Datos actuales (sin usar datos demo)

- **18 equipos (con Pachuca), 611 jugadores reales de Liga MX 2026-27**:
  rosters completos vía ESPN.
- **95 partidos y 3.147 player_stats** reales (jornadas del Apertura vía ESPN).
- Próximo partido **Necaxa vs Juárez** (2026-10-24) con picks y convocatorias;
  agenda de la semana completa ingesta T-24h automática.
- Límite honesto: los features usan sólo partidos anteriores al kickoff
  (corte anti-fuga). El backtest muestra que la calibración en cola
  izquierda/percentiles altos es optimista; se mejorará en iteraciones.
  Reglas aún PROVISIONAL: cargar `config/contest_rules.json` con las reales.

### Resultados del backtest (ventana 14 partidos, 587 filas, 2026-10-22)

| Métrica | Valor |
|---|---|
| MAE puntos (mediana del modelo, jugando) | 2.95 |
| Baseline (mediana global constante) | 2.95 → el modelo empata baseline en media, gana por separación por posición (DEF 2.27, MID 2.76 vs FWD 3.69, GK 4.23) |
| MAE minutos esperados | 26.8 (alto: aún sin modelo de rotación fino) |
| Cobertura p25/p50/p75/p90 observada | 0.62 / 0.53 / 0.43 / 0.29 (esperado 0.75/0.5/0.25/0.10 → optimista en colas) |
| Brier por umbral 4/6/8 | 0.34 / 0.14 / 0.12 |
| Calibración titularidad (bins 0-0.5/0.5-0.8/0.8+) | 0.27 / 0.58 / 0.89 observado — bien calibrado |

### Cómo correr (local, ya funciona)

```bash
cd backend && uv sync
PICKMASTER_DATABASE_URL=sqlite:///./pickmaster.db uv run python -m app.worker.cli ingest-online
PICKMASTER_DATABASE_URL=... uv run python -m app.worker.cli generate-picks --match 1

cd frontend && npm install
cd frontend && npm run dev        # proxy al API: configuras .env PUBLIC_API_URL
cd frontend && npm run build       # adapter-node listo para Docker
```

Pendiente: reglas exactas del concurso de Draftea (manual →
`config/contest_rules.json`). Los pesos provisionales se marcan como tal
en `/api/health`.
