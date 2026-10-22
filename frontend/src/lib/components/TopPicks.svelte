<script lang="ts">
  /** Top picks: tarjetas compactas con insignia de camiseta y barra fina. */
  import PlayerBadge from "./PlayerBadge.svelte";

  type TopPick = {
    player: string;
    player_id: number;
    position: string;
    expected_points: number;
    probability: number;
    confidence: number;
    why: string[];
    gold_status: string;
  };
  type Props = { top: TopPick[] };
  let { top }: Props = $props();
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
          <div class="tarjeta-top__fila">
            <span class="row-pick__badge" style="width:44px">
              <PlayerBadge name={p.player} position={p.position} gold />
            </span>
            <div>
              <h3>{p.player}</h3>
              <span class="chip chip--{p.position}">{p.position}</span>
            </div>
            <div class="tarjeta-top__pts">
              <strong>{p.expected_points.toFixed(1)}</strong>
              <span>pts esperados</span>
            </div>
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
        </li>
      {/each}
    </ul>
  {/if}
</section>
