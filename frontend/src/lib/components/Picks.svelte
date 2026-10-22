<script lang="ts">
  import Chibi from "$lib/components/Chibi.svelte";
  import { fraseAleatoria, frasesPicks } from "$lib/phrases";

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

  const frase = fraseAleatoria(frasesPicks);
</script>

<section>
  <h2>🎯 Picks del partido</h2>
  <p class="subtitulo">{frase.titulo} — {frase.quote}</p>

  {#if picks.length === 0}
    <p class="meta">Pizarra en blanco: a la espera del modelo (y del XI confirmado).</p>
  {:else}
    <ul class="tarjetas">
      {#each picks as p (p.player_id)}
        <li class="tarjeta">
          <div class="fila">
            <div class="chibi-box"><Chibi name={p.player} position={p.position} /></div>
            <div>
              <h3>{p.player}</h3>
              <span class="chapita chapita--{p.position}">{p.position}</span>
            </div>
          </div>
          <p class="meta">
            Esp.: <strong>{p.expected_points.toFixed(1)}</strong> pts ·
            target: {p.target_points.toFixed(1)} ·
            prob.: {Math.round(p.probability * 100)}%
          </p>
          {#if p.reason}
            <p class="meta razon">{p.reason}</p>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .fila { display: flex; gap: 0.6rem; align-items: center; }
  .chibi-box { width: 56px; flex-shrink: 0; }
  h3 { font-size: 0.98rem; margin: 0 0 0.25rem; }
  .razon { font-size: 0.8rem; font-style: italic; opacity: 0.92; }
</style>
