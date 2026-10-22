<script lang="ts">
  /** Picks por posición: filas compactas al estilo lista nativa. */
  import PlayerBadge from "$lib/components/PlayerBadge.svelte";

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
  type Props = { picks: Pick[] };
  let { picks }: Props = $props();

  const POSICIONES = ["GK", "DEF", "MID", "FWD"];
  const POS_NAMES: Record<string, string> = {
    GK: "Porteros",
    DEF: "Defensas",
    MID: "Medios",
    FWD: "Delanteros",
  };
</script>

<section class="section">
  <div class="section__head">
    <h2>Picks del partido</h2>
    <span class="section__tag">por posición</span>
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
              <li class="card row-pick">
                <span class="row-pick__badge"><PlayerBadge name={p.player} position={p.position} /></span>
                <div>
                  <span class="row-pick__name">{p.player}</span>
                  {#if p.reason}
                    <p class="row-pick__why">{p.reason}</p>
                  {/if}
                </div>
                <div class="row-pick__num">
                  <strong>{p.expected_points.toFixed(1)}</strong>
                  <span>prob. {Math.round(p.probability * 100)}%</span>
                </div>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    {/each}
  {/if}
</section>
