<script lang="ts">
  import Lineups from "$lib/components/Lineups.svelte";
  import Picks from "$lib/components/Picks.svelte";
  import TopPicks from "$lib/components/TopPicks.svelte";
  import { fraseAleatoria, frasesCarga } from "$lib/phrases";

  let { data } = $props();
  const cargaFrase = fraseAleatoria(frasesCarga);
</script>

{#if data.estado === "ok"}
  {#if data.partidoId}
    <h2>El duelo: partido #{data.partidoId}</h2>
    <p class="subtitulo">Picks regenerados en cada consulta del banquillo ⚽</p>
    <TopPicks top={data.top ?? []} />
    <Picks picks={data.picks ?? []} />
    <Lineups teams={data.teams ?? []} />
  {/if}
{:else if data.estado === "vacio"}
  <div class="velocidad">
    <h2>{data.frase?.titulo}</h2>
    <p class="subtitulo">{data.frase?.quote}</p>
  </div>
{:else}
  <div class="velocidad">
    <h2>{data.frase?.titulo ?? "Pitazo anulado"}</h2>
    <p class="subtitulo">{data.frase?.quote}</p>
    <p class="meta">Revisa que la API esté corriendo (uvicorn app.main:app --port 8000).</p>
  </div>
{/if}

{#if data.estado !== "ok"}
  <noscript>
    <p class="meta">{cargaFrase.titulo} — {cargaFrase.quote}</p>
  </noscript>
{/if}
