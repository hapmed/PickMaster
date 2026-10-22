<script lang="ts">
  /** Top picks: tarjetas compactas; tap/click despliega la proyección (goles, asistencias, ...). */
  import PlayerBadge from "$lib/components/PlayerBadge.svelte";
  import ProjectionDetail from "$lib/components/ProjectionDetail.svelte";

  type TopPick = {
    player: string;
    player_id: number;
    position: string;
    expected_points: number;
    probability: number;
    confidence: number;
    why?: string[];
    statistics?: {
      expected_events?: Record<string, number> | null;
      minutes_expected?: number | null;
      start_probability?: number | null;
      mean?: number | null;
      p90?: number | null;
    } | null;
  };
  type Props = { top: TopPick[]; matchId: number };
  let { top, matchId }: Props = $props();

  let abiertas = $state<Set<number>>(new Set());

  function alternar(id: number) {
    const sig = new Set(abiertas);
    if (sig.has(id)) {
      sig.delete(id);
    } else {
      sig.add(id);
    }
    abiertas = sig;
  }
</script>

<section class="section">
  <div class="section__head">
    <h2>Top picks</h2>
    <span class="section__tag">ordenados por probabilidad × puntos × confianza</span>
  </div>

  {#if top.length === 0}
    <div class="card centrado">
      <p class="meta">Sin picks sobre el umbral todavía — se afinan en T-1h con el XI confirmado.</p>
    </div>
  {:else}
    <ul class="tarjetas-top">
      {#each top as p (p.player_id)}
        <li class="card tarjeta-top">
          <button
            type="button"
            class="tarjeta-top__btn"
            aria-expanded={abiertas.has(p.player_id)}
            onclick={() => alternar(p.player_id)}
          >
            <div class="tarjeta-top__fila">
              <span class="row-pick__badge" style="width:44px">
                <PlayerBadge name={p.player} position={p.position} gold />
              </span>
              <span>
                <h3>{p.player}</h3>
                <span class="chip chip--{p.position}">{p.position}</span>
              </span>
              <span class="tarjeta-top__pts">
                <strong>{p.expected_points.toFixed(1)}</strong>
                <span>pts esperados</span>
              </span>
            </div>
            <div class="mini-barra" style="--marcador: {Math.round(p.probability * 100)}">
              <span></span>
            </div>
            <p class="meta">
              prob. {Math.round(p.probability * 100)}% · confianza {Math.round(p.confidence * 100)}%
            </p>
            {#each (p.why ?? []).slice(0, 2) as w}
              <p class="row-pick__why">{w}</p>
            {/each}
          </button>
          {#if abiertas.has(p.player_id)}
            <ProjectionDetail playerId={p.player_id} matchId={matchId} pre={p.statistics ?? null} />
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .tarjeta-top__btn {
    display: grid;
    gap: 8px;
    width: 100%;
    background: none;
    border: 0;
    font: inherit;
    color: inherit;
    text-align: left;
    cursor: pointer;
    border-radius: inherit;
  }
  .tarjeta-top__btn:hover {
    background: var(--hover);
  }
</style>
