<script lang="ts">
  import MatchPrediction from "$lib/components/MatchPrediction.svelte";
  import Picks from "$lib/components/Picks.svelte";
  import TopPicks from "$lib/components/TopPicks.svelte";

  let { data } = $props();

  const upcoming = $derived(
    (data.matches ?? []).filter((m: any) => m.status === "scheduled").slice(0, 10)
  );
  const actual = $derived(data.partidoId);
  const matchLabel = (m: any) =>
    `${m.home.slice(0, 3).toUpperCase()}–${m.away.slice(0, 3).toUpperCase()}`;
</script>

{#if data.estado === "ok" && data.partidoId}
  {#if upcoming.length > 1}
    <nav class="seg" aria-label="Selector de partido">
      {#each upcoming as m (m.id)}
        <a href={`/?partido=${m.id}`} class:activo={m.id === actual}>
          {matchLabel(m)} · {m.kickoff.slice(5, 10)}
        </a>
      {/each}
    </nav>
  {/if}

  <MatchPrediction pronostico={data.pronostico ?? null} />
  <TopPicks top={data.top ?? []} matchId={data.partidoId} />
  <Picks picks={data.picks ?? []} matchId={data.partidoId} />
{:else if data.estado === "vacio"}
  <div class="card centrado section">
    <h2>Sin partidos</h2>
    <p class="meta">{data.frase?.quote ?? ""}</p>
  </div>
{:else}
  <div class="card centrado section">
    <h2>API sin responder</h2>
    <p class="meta">Esperando la conexión con el servidor.</p>
  </div>
{/if}
