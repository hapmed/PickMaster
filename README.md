# Drafteando

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
- Dominio: `drafteando.hapmed.qzz.io`
- Repo: `hapmed/Drafteando`
- Base: `drafteando` en el PostgreSQL existente

## Documentación

- [`AGENTS.md`](./AGENTS.md) — brief completo para el agente.
- [`ACCESOS.md`](./ACCESOS.md) — servidor, BD, GitHub, Cloudflare, R2 y SMB.
- [`docs/ARQUITECTURA.md`](./docs/ARQUITECTURA.md) — pipeline, API y datos.
- [`docs/MODELO.md`](./docs/MODELO.md) — features, modelos, calibración y backtest.
- [`docs/FUENTES_DATOS.md`](./docs/FUENTES_DATOS.md) — fuentes legales y límites.
- [`config/contest_rules.example.json`](./config/contest_rules.example.json) — reglas a completar.

## Estado

Especificación lista. **Implementación pendiente.**

Pendiente de definir: fuente de datos y reglas exactas del concurso de Draftea.
