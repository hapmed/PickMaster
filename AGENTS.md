# AGENTS.md — Drafteando

Guía obligatoria para el agente que programe este proyecto.

## 0. Regla de oro

- Trabaja **solo** dentro de `/proyectos/Drafteando`.
- **No** toques otros proyectos ni las bases `hapmed` / `evas_admin`.
- Los secretos están en [`ACCESOS.md`](./ACCESOS.md): úsalos, **no los versiones**,
  no los pegues en logs ni en el chat.
- GitHub: cuenta **`hapmed`** (credencial en `/root/.git-credentials`).
  `hector1516` es solo para consultas de lectura.
- **Nada de scraping de Draftea** ni automatización de entradas. Reglas y salarios
  se cargan manualmente o desde un CSV autorizado.
- Es un proyecto de análisis para adultos. No prometas ganancias ni aciertos.

## 1. Qué es

**Drafteando** entrega **picks probabilísticos** para concursos de **Draftea ·
Liga MX**. Antes de cada partido muestra los jugadores con mayor probabilidad y
puntos esperados, con confianza y explicación.

- Solo **Liga MX** por ahora.
- Un partido a la vez; picks por posición.
- Actualización T-24h, T-6h y T-1h (alineaciones).
- Dashboard web + API.
- Backtesting con torneos anteriores.

## 2. Decisiones cerradas

| Tema | Decisión |
|---|---|
| Liga | Liga MX |
| Plataforma | Draftea |
| Salida | Picks por probabilidad, puntos esperados y confianza |
| Hosting | HomeLab (`192.168.0.14`) |
| Web | `127.0.0.1:8087` |
| Dominio | `drafteando.hapmed.qzz.io` |
| BD | `drafteando` en PostgreSQL existente |
| Stack | Python + FastAPI + PostgreSQL + SvelteKit |

## 3. Arquitectura

```
Fuentes de datos (API/CSV)
        │
        ▼
  ingesta + normalización
        │
        ▼
  features + modelos + Monte Carlo
        │
        ▼
  picks + confianza + explicación
        │
        ├── PostgreSQL
        ├── API FastAPI
        └── Dashboard SvelteKit
```

- `worker`: ingesta, entrenamiento y generación de picks.
- `api`: consultas y administración.
- `web`: dashboard.
- `redis`: colas/caché.
- Sin scraping de Draftea.

## 4. Flujo antes de cada partido

1. **T-24h:** fixtures, historial, lesiones y probables alineaciones.
2. **T-6h:** actualización de noticias y cuotas legales si existen.
3. **T-1h:** alineaciones confirmadas; recalcular picks y marcar confianza.
4. **Publicación:** top picks por posición, con puntos esperados, probabilidad,
   rango y explicación.
5. **Post-partido:** guardar resultado real y evaluar la proyección.

## 5. Modelo

### Minutos
- Probabilidad de titularidad.
- Minutos esperados y distribución.
- Descanso, lesión, sanción, rotación y contexto del partido.

### Eventos
- Goles y asistencias: Poisson/negativo binomial.
- Tiros a puerta, pases clave, entradas, paradas: clasificación/regresión.
- Tarjetas y autogoles: probabilidades históricas ajustadas.
- Fuerza del rival, local/visitante, ritmo y estilo.

### Puntos fantasy
- Configurables en `config/contest_rules.json`.
- **No asumir** los valores de Draftea: completarlos con las reglas vigentes.
- Suma de eventos × pesos.
- Monte Carlo (10,000 simulaciones por jugador) para media, mediana, p10/p90.

### Picks
- Ordenar por puntos esperados.
- Valor: puntos esperados por salario.
- Probabilidad de superar un umbral (ej. 4, 6, 8 puntos).
- Confianza según datos y lesiones.
- Diversificación para no llenar la alineación con un solo equipo.
- Explicación: “titular, buen matchup, alta participación”.

### Calibración y backtest
- Entrenar con torneos anteriores; validar con un torneo distinto.
- Métricas: MAE de puntos, log loss/Brier para umbrales, calibración.
- Simulación de percentiles frente a un campo sintético.
- Reporte reproducible por jornada.
- Sin fuga de datos: solo información disponible antes del partido.

## 6. Fuentes de datos

- API-Football, Football-Data.org o TheSportsDB para fixtures/estadísticas.
- Datos oficiales de Liga MX si están disponibles y permitidos.
- CSV manual para reglas, salarios y alineaciones.
- **No** scrapear Draftea, SofaScore ni sitios que lo prohíban.
- Respetar términos de uso y licencias.
- Guardar la fecha/hora de cada dato para auditoría.

## 7. API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/health` | Salud |
| `GET` | `/api/matches` | Partidos de la jornada |
| `GET` | `/api/matches/{id}` | Detalle |
| `GET` | `/api/picks?match_id=` | Picks del partido |
| `GET` | `/api/players/{id}/projection` | Proyección del jugador |
| `GET` | `/api/backtest` | Resultados del backtest |
| `POST` | `/api/admin/refresh` | Forzar actualización |

## 8. Datos

- `teams`, `players`, `matches`, `player_stats`, `lineups`, `injuries`.
- `projections`: jugador, partido, media, mediana, p10, p90, confianza.
- `picks`: partido, jugador, posición, puntos esperados, probabilidad, motivo.
- `model_runs`: versión, fecha, métricas.
- `contest_rules`: reglas y salarios cargados.
- `audit_log`: cambios manuales.

## 9. Dashboard

- Partidos de la jornada y hora.
- Picks por posición con probabilidad y puntos esperados.
- Detalle del jugador: forma, minutos, matchup y riesgo.
- Semáforo de confianza.
- Historial de aciertos y calibración.
- Aviso visible: “No garantiza resultados. Juega con responsabilidad.”

## 10. Fases

### Fase 1 — Datos y proyecciones
- Ingesta de equipos, jugadores y partidos.
- Histórico de estadísticas.
- Modelo de minutos y puntos.
- Picks por partido en JSON.
- CLI o endpoint para generar picks.

### Fase 2 — Dashboard
- SvelteKit con jornada, picks y detalle.
- Filtros por posición y confianza.
- Historial y backtest.
- Responsive.

### Fase 3 — Automatización
- Jobs T-24h/T-6h/T-1h.
- Alertas de lesiones/alineaciones.
- Actualización de picks.
- Registro de resultados.

### Fase 4 — Mejora
- Más features y modelos.
- Calibración avanzada.
- Comparación con baseline.
- Explicabilidad.

## 11. Aceptación de Fase 1

- [ ] Se cargan equipos, jugadores y partidos de Liga MX.
- [ ] Se calculan minutos esperados y puntos proyectados.
- [ ] Se generan picks por partido y posición.
- [ ] Cada pick incluye probabilidad, puntos esperados y confianza.
- [ ] Backtest con un torneo anterior.
- [ ] No hay fuga de datos.
- [ ] No hay secretos en Git.

## 12. Verificación

```bash
cd backend && uv sync && uv run ruff check . && uv run mypy app && uv run pytest
cd frontend && npm install && npm run check && npm run lint && npm run test && npm run build
docker compose -f ops/compose.yaml config
```

Si el entorno no tiene Node/Python, usar Docker o el servidor. **No reportar como
verificado lo que no se ejecutó.**

## 13. Ética y responsabilidad

- Solo mayores de edad.
- No es asesoría financiera ni garantía de resultados.
- No automatizar apuestas ni saltar límites de la plataforma.
- Respetar los términos de Draftea y la legislación local.
- Mostrar siempre la incertidumbre; nunca vender certeza.
- Incluir mensajes de juego responsable.

## 14. Bloqueos conocidos

- Falta elegir fuente de datos y API key.
- Faltan las reglas exactas del concurso de Draftea.
- Node/Python no están instalados en el contenedor de opencode.
- Falta crear la base `drafteando`.
- Falta configurar DNS.

## 15. Reporte al terminar

1. Qué se implementó y qué no.
2. Archivos creados/modificados.
3. Comandos ejecutados y salida real.
4. Backtest y métricas.
5. Bloqueos y siguiente paso.
