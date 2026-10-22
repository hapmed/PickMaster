<script lang="ts">
  import Chibi from "./Chibi.svelte";
  import { fraseAleatoria, frasesProbables } from "$lib/phrases";

  type TopPick = {
    player: string;
    player_id: number;
    position: string;
    expected_points: number;
    target_points: number;
    probability: number;
    confidence: number;
    why: string[];
    gold_status: string;
  };
  type Props = { top: TopPick[] };
  let { top }: Props = $props();

  const frase = fraseAleatoria(frasesProbables);
</script>

<section class="velocidad">
  <h2>⚡ {frase.titulo} <span class="estrella">★</span></h2>
  <p class="subtitulo">{frase.quote}</p>

  {#if top.length === 0}
    <p class="meta">Nadie superó el umbral: hasta el D.T. duda. Vuelve en T-1h.</p>
  {:else}
    <ul class="tarjetas">
      {#each top as p, i (p.player_id)}
        <li class="tarjeta tarjeta--ping">
          <div class="fila">
            <div class="chibi-box"><Chibi name={p.player} position={p.position} gold numero={10 + i} /></div>
            <div>
              <h3>{p.player}</h3>
              <span class="chapita chapita--{p.position}">{p.position}</span>
              <span class="chapita">{p.gold_status}</span>
            </div>
          </div>
          <p class="meta">
            Esperados: <strong>{p.expected_points.toFixed(1)}</strong> pts ·
            prob.: <strong>{Math.round(p.probability * 100)}%</strong> ·
            confianza: {Math.round(p.confidence * 100)}%
          </p>
          <div class="barra" style="--marcador: {Math.round(p.probability * 100)}">
            <span class="barra__marcador"></span>
          </div>
          <h4>¿Por qué?</h4>
          <ul class="por-que">
            {#each p.why as w}
              <li>{w}</li>
            {/each}
          </ul>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .fila { display: flex; gap: 0.7rem; align-items: center; }
  .chibi-box { width: 64px; flex-shrink: 0; }
  h3 { font-size: 1rem; margin: 0 0 0.25rem; }
  h4 { font-size: 0.85rem; margin: 0.7rem 0 0.2rem; }
</style>
