<script lang="ts">
  /**
   * Detalle expandible de proyección: eventos esperados, minutos y rango.
   * Carga la proyección solo la primera vez que se abre (fetch perezoso).
   */
  import { api, type Proyeccion } from "$lib/api";

  type Props = {
    playerId: number;
    matchId: number;
    /** Datos ya disponibles (top picks los traen en `statistics`); evita el fetch. */
    pre?: {
      expected_events?: Record<string, number> | null;
      minutes_expected?: number | null;
      start_probability?: number | null;
      mean?: number | null;
      p90?: number | null;
    } | null;
  };

  let { playerId, matchId, pre = null }: Props = $props();

  let proyeccion = $state<Proyeccion | null>(null);
  let cargado = $state(false);

  $effect(() => {
    if (cargado) return;
    cargado = true;
    if (pre) return;
    void api
      .projection(playerId, matchId)
      .then((p) => (proyeccion = p))
      .catch(() => (proyeccion = null));
  });

  const ev = $derived(pre?.expected_events ?? proyeccion?.expected_events ?? {});
  const minutos = $derived(pre?.minutes_expected ?? proyeccion?.minutes_expected);
  const titular = $derived(pre?.start_probability ?? proyeccion?.start_probability);

  const EVENTOS: Array<{ key: string; label: string }> = [
    { key: "goals", label: "Goles" },
    { key: "assists", label: "Asistencias" },
    { key: "shots_on_target", label: "Tiros a puerta" },
    { key: "key_passes", label: "Pases clave" },
    { key: "tackles", label: "Entradas" },
    { key: "saves", label: "Paradas" },
  ];

  const iconos: Record<string, string> = {
    goals: "⚽",
    assists: "🅰️",
    shots_on_target: "🎯",
    key_passes: "🧵",
    tackles: "🛡️",
    saves: "🧤",
  };
</script>

<div class="detalle">
  {#if ev && Object.keys(ev).length}
    <div class="detalle__grid">
      {#each EVENTOS as e}
        <div class="metrica">
          <span class="metrica__valor">{ev[e.key] != null ? ev[e.key].toFixed(2) : "—"}</span>
          <span class="metrica__etiqueta">{iconos[e.key]} {e.label}</span>
        </div>
      {/each}
    </div>
  {:else}
    <p class="meta">Sin desglose de eventos para este jugador todavía.</p>
  {/if}

  <div class="detalle__fila">
    {#if minutos != null}
      <span class="metrica-sec"><strong>{minutos.toFixed(0)}</strong> min esperados</span>
    {/if}
    {#if titular != null}
      <span class="metrica-sec"><strong>{Math.round(titular * 100)}%</strong> titularidad</span>
    {/if}
    <span class="detalle__fuente">Monte Carlo · no garantiza resultados</span>
  </div>
</div>

<style>
  .detalle {
    padding: 2px 12px 10px 52px;
    display: grid;
    gap: 8px;
  }
  .detalle__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    gap: 6px;
  }
  .metrica {
    display: grid;
    align-items: center;
    background: transparent;
    border: 1px solid var(--hairline);
    border-radius: 10px;
    padding: 6px 10px;
    line-height: 1.15;
  }
  .metrica__valor {
    font-size: 1rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .metrica__etiqueta {
    font-size: 0.72rem;
    color: var(--ink-2);
  }
  .detalle__fila {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 14px;
    font-size: 0.75rem;
    color: var(--ink-2);
  }
  .metrica-sec strong {
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .detalle__fuente {
    margin-left: auto;
    font-size: 0.72rem;
  }
</style>
