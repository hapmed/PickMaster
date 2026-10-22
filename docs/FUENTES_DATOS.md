# Fuentes de datos — PickMaster

## Prioridad

1. API oficial o con licencia.
2. Datos abiertos con términos permitidos.
3. CSV/manual para reglas, salarios y alineaciones.
4. Nunca scraping de Draftea.

## Opciones

| Fuente | Datos | Acceso | Notas |
|---|---|---|---|
| **ESPN (site.api)** | Fixtures, resultados, alineaciones, stats por jugador por partido | Sin key, endpoint público de su web | **No oficial**: uso mínimo/respetuoso (3 llamadas por partido, UA identificable, pausa 3s). El 2026-10-22 entrega Liga MX completa |
| **API-Football** | Fixtures, stats, lineups, injuries | API key (free/paid) | Cobertura amplia; revisar plan |
| **Football-Data.org** | Fixtures, resultados, tablas | API key gratuita limitada | Buena base para empezar |
| **TheSportsDB** | Equipos, jugadores, básicos | Key gratuita | Datos limitados (1 próximo/pasado evento; sin stats por jugador) |
| **Liga MX oficial** | Calendario, resultados | Web/posible API | Revisar términos |
| **FBref** | Estadísticas históricas | Web | Revisar términos antes de scrapear |
| **Draftea** | Reglas, salarios, concursos | App/Web | **Manual**; sin scraping ni automatización |

## Reglas de uso

- Respetar los términos de cada fuente.
- Guardar la fecha de cada dato.
- No redistribuir datos de pago.
- No scrapear sitios que lo prohíban.
- Si una fuente falla, usar caché y marcar la confianza como baja.

## Datos mínimos para el MVP

- Equipos y jugadores de Liga MX.
- Calendario del torneo.
- Estadísticas por partido: minutos, goles, asistencias, tiros, pases clave,
  entradas, paradas, tarjetas.
- Lesiones/sanciones y probables alineaciones.
- Reglas de puntuación del concurso.
- Salarios de los jugadores (manual/CSV).

## Post-partido

- Estadísticas finales: minutos, goles, asistencias, tiros, pases clave,
  entradas, paradas, tarjetas y goles recibidos.
- Pueden tardar; reintentar a T+1h y T+3h.
- Calcular puntos reales con las reglas del concurso.
- Comparar con la proyección y guardar `pick_results`.
- Si el jugador no jugó, marcar `no_play`, no `miss`.

## Calidad

- Validar que los minutos sumen.
- Detectar jugadores duplicados.
- Normalizar nombres y equipos.
- Marcar datos faltantes en vez de inventarlos.
- Versionar las reglas del concurso.
