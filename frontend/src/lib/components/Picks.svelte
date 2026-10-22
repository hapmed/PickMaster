<script lang="ts">
  /** Picks por posición: filas compactas; tap/click despliega la proyección (goles, asistencias, ...). */
  import PlayerBadge from "$lib/components/PlayerBadge.svelte";
  import ProjectionDetail from "$lib/components/ProjectionDetail.svelte";

  type Pick = {
    player: string;
    player_id: number;
    position: string;
    expected_points: number;
    target_points: number;
    probability: number;
    confidence: number;
    reason: string | null;
  };
  type Props = { picks: Pick[]; matchId: number };
  let { picks, matchId }: Props = $props();

  let abiertas = $state<Set<number>>(new Set());

  const POSICIONES = ["GK", "DEF", "MID", "FWD"];
  const POS_NAMES: Record<string, string> = {
    GK: "Porteros",
    DEF: "Defensas",
    MID: "Medios",
    FWD: "Delanteros",
  };

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
    <h2>Picks del partido</h2>
    <span class="section__tag">por posición · toca para ver goles y más</span>
  </div>

  {#if picks.length === 0}
    <div class="card centrado">
      <p class="meta">A la espera del modelo y del XI confirmado.</p>
    </div>
  {:else}
    {#each POSICIONES as pos}
      {@const enPos = picks.filter((p) => p.position === pos)}
      {#if enPos.length}
        <div class="pos-bloque">
          <p class="pos-titulo">{POS_NAMES[pos]}</p>
          <ul class="rows">
            {#each enPos as p (p.player_id)}
              <li class="card fila-pick">
                <button
                  type="button"
                  class="row-pick fila-pick__btn"
                  aria-expanded={abiertas.has(p.player_id)}
                  onclick={() => alternar(p.player_id)}
                >
                  <span class="row-pick__badge"><PlayerBadge name={p.player} position={p.position} /></span>
                  <span class="fila-pick__texto">
                    <span class="row-pick__name">{p.player}</span>
                    {#if p.reason}
                      <span class="row-pick__why">{p.reason}</span>
                    {/if}
                  </span>
                  <span class="row-pick__num">
                    <strong>{p.expected_points.toFixed(1)}</strong>
                    <span>prob. {Math.round(p.probability * 100)}%</span>
                  </span>
                  <span class="fila-pick__flecha" class:arriba={abiertas.has(p.player_id)}>⌄</span>
                </button>
                {#if abiertas.has(p.player_id)}
                  <ProjectionDetail playerId={p.player_id} matchId={matchId} />
                {/if}
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    {/each}
  {/if}
</section>

<style>
  .fila-pick {
    overflow: hidden;
  }
  .fila-pick__btn {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 12px;
    background: none;
    border: 0;
    font: inherit;
    color: inherit;
    text-align: left;
    cursor: pointer;
  }
  .fila-pick__btn:hover {
    background: var(--hover);
  }
  .fila-pick__texto {
    min-width: 0;
    display: grid;
    gap: 1px;
  }
  .fila-pick__flecha {
    flex-shrink: 0;
    color: var(--ink-2);
    font-size: 0.9rem;
    transition: transform 0.2s ease;
  }
  .fila-pick__flecha.arriba {
    transform: rotate(180deg);
  }
</style>
