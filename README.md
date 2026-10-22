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

**Fases 1–3 implementadas** (Fase 4 pendiente de datos históricos reales).

| Bloque | Estado |
|---|---|
| Backend FastAPI + SQLAlchemy (todas las rutas de la tabla API) | ✅ |
| Motor de proyección: minutos + eventos + Monte Carlo 10k | ✅ determinista |
| Picks por posición + **SELECCIÓN 5 ESTRELLAS** (probabilidad × puntos × confianza, con sección "¿Por qué?") | ✅ `/api/picks/top` |
| Evaluación post-partido ✅🟡❌⚪ + hit rate + reporte | ✅ |
| Ingesta manual por CSV (reglas, salarios, XI confirmado) | ✅ |
| **Ingesta online TheSportsDB** (equipos + jugadores + calendario Liga MX, key pública `123`, acumulativa y respetando 429) | ✅ con datos reales |
| Alineaciones/convocatorias estimadas del roster (`/api/lineups`) | ✅ |
| Dashboard SvelteKit estilo **Super Campeones**: chibis SVG por jugador (determinista), alineaciones por posición probables, picks top con "¿Por qué?", mensajes hilarantes en carga/errores/estados vacíos | ✅ build OK |
| Scheduler Fase 3 (T-24h / T-6h / T-1h + evaluación post-partido con ledger `worker_jobs`) | ✅ testado |
| Notificación Telegram/email (interesados: env por claves) | ✅ módulo listo; sin credencial es irrelevante en dashboard |
| Lint/mypy/pytest backend | ✅ 26 tests · ruff · mypy strict |
| Dashboard checks | ✅ svelte-check 0 errors · vitest · vite build |
| **Despliegue HomeLab** (compose `pickmaster_*` en apps-net, BD Postgres `pickmaster`, túnel Cloudflare con regla aditiva) | ✅ vivo en `pickmaster.hapmed.qzz.io` |
| Backtest con torneos anteriores | ⬜ bloqueado por falta de datos históricos por jugador |

### Datos actuales (sin usar datos demo)

- **17 equipos, ~135 jugadores reales de Liga MX 2026-27** (ingesta TheSportsDB;
  Mazatlán rescatado por id directo por una rareza del free tier).
- Próximo partido **Necaxa vs Juárez** (2026-10-24) con picks reales generados
  y convocatorias por posición.
- Límite honesto: sin estadísticas evento-a-evento del free tier la confianza
  sale **35%** y las menciones de "pocos datos históricos" son correctas.
  Con una API key premium (API-Football/Statful) se elevaría la precisión.

### Cómo correr (local, ya funciona)

```bash
cd backend && uv sync
PICKMASTER_DATABASE_URL=sqlite:///./pickmaster.db uv run python -m app.worker.cli ingest-online
PICKMASTER_DATABASE_URL=... uv run python -m app.worker.cli generate-picks --match 1

cd frontend && npm install
cd frontend && npm run dev        # proxy al API: configuras .env PUBLIC_API_URL
cd frontend && npm run build       # adapter-node listo para Docker
```

Pendiente de definir: fuente de datos y reglas exactas del concurso de Draftea.
