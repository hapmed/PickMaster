# Modelo — Drafteando

## Objetivo

Estimar, antes de cada partido de Liga MX, la **distribución de puntos fantasy**
de cada jugador según las reglas del concurso de Draftea. Los picks se ordenan
por probabilidad y puntos esperados, no por corazonadas.

## Pipeline

```
datos históricos + contexto del partido
        │
        ▼
features por jugador
        │
        ├── modelo de minutos
        ├── modelos de eventos (goles, asistencias, tiros, paradas...)
        └── reglas de puntuación
        │
        ▼
Monte Carlo → distribución de puntos
        │
        ▼
ranking + valor + confianza + explicación
```

## Features

- Minutos y titularidad en los últimos 3/5/10 partidos.
- Goles, asistencias, tiros, pases clave, entradas, paradas y tarjetas por 90.
- Local/visitante.
- Fuerza defensiva y ofensiva del rival.
- Ritmo y estilo del equipo.
- Descanso entre partidos y viajes.
- Lesiones, sanciones y probables alineaciones.
- Posición y rol.
- Historial contra el rival.
- Contexto: importancia del partido, rotación, clima.

## Modelo de minutos

- Probabilidad de ser titular.
- Distribución de minutos (0, 15, 45, 60, 90...).
- Ajuste por lesión, sanción, rotación y urgencia del equipo.
- Es la variable más importante: sin minutos no hay puntos.

## Modelo de eventos

- Goles y asistencias: Poisson o binomial negativa ajustada por tasa y rival.
- Tiros a puerta, pases clave, entradas y paradas: regresión/clasificación.
- Tarjetas y autogoles: probabilidad histórica ajustada.
- Porteros: paradas, valla invicta, goles recibidos.
- Defensas: despejes, entradas, duelos y goles recibidos.

## Puntos fantasy

- Se calculan con `config/contest_rules.json`.
- Cada evento se multiplica por su peso.
- **No se asumen** los valores de Draftea; deben completarse con las reglas
  vigentes del concurso.
- Se calcula la distribución completa, no solo la media.

## Monte Carlo

- 10,000 simulaciones por jugador.
- Se muestrean minutos, eventos y puntos.
- Salida: media, mediana, p10, p90, probabilidad de superar umbrales.
- Permite comparar jugadores con distinto riesgo.

## Picks

- Ordenar por puntos esperados.
- Valor: puntos esperados por unidad de salario.
- Probabilidad de alcanzar un umbral (ej. 4, 6, 8 puntos).
- Confianza: calidad de datos, certeza de alineación y estabilidad histórica.
- Diversificación por equipo y posición.
- Explicación breve por pick.

## Calibración

- Comparar probabilidad predicha vs frecuencia observada.
- Reliability diagram, Brier score y log loss.
- Ajustar probabilidades con calibración isotónica o Platt si hace falta.
- No basta con “acertar”: importa que las probabilidades sean honestas.

## Backtest

- Entrenar con torneos anteriores.
- Validar con un torneo distinto (holdout temporal).
- Métricas: MAE de puntos, correlación, Brier, log loss, calibración.
- Simulación de percentiles frente a un campo sintético.
- Reporte por jornada y por posición.

## Riesgos y límites

- Datos incompletos o tardíos.
- Alineaciones confirmadas a última hora.
- Sobreajuste a un torneo.
- Cambios de reglas o salarios.
- La incertidumbre del deporte no se elimina.
- El modelo puede estar bien calibrado y aun así perder en una jornada.

## Baseline

Antes de un modelo complejo, comparar contra:

- Promedio de los últimos 5 partidos.
- Media por posición.
- Modelo simple de minutos × tasa histórica.

Si el modelo no supera el baseline en backtest, no se publica.
