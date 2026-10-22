<script lang="ts">
  /** Pronóstico: quién gana, marcador probable y quién anota (Poisson). */
  import type { Pronostico } from "$lib/api";

  type Props = { pronostico: Pronostico | null };
  let { pronostico }: Props = $props();

  const pct = (v: number) => `${Math.round(v * 100)}%`;
  const corta = (n: string, max = 12) => (n.length > max ? `${n.slice(0, max)}…` : n);

  const opciones = $derived(
    pronostico
      ? [
          { label: `Gana ${corta(pronostico.home)}`, v: pronostico.p_home },
          { label: "Empate", v: pronostico.p_draw },
          { label: `Gana ${corta(pronostico.away)}`, v: pronostico.p_away },
        ]
      : []
  );
  const max = $derived(Math.max(...opciones.map((o) => o.v)));
</script>

{#if pronostico}
  <section class="section">
    <div class="section__head">
      <h2>Predicción del partido</h2>
      <span class="section__tag">Poisson con historial previo · no garantiza nada</span>
    </div>

    <div class="card pron">
      <div class="pron__gana">
        {#each opciones as o (o.label)}
          <div class="pron__chip" class:activo={o.v === max}>
            {o.label} <strong>{pct(o.v)}</strong>
          </div>
        {/each}
      </div>

      <div class="pron__marcador">
        <span class="pron__gol">{pronostico.home_goals_expected.toFixed(1)} goles esperados</span>
        <strong class="pron__score">{pronostico.most_likely_score[0]} – {pronostico.most_likely_score[1]}</strong>
        <span class="pron__gol">{pronostico.away_goals_expected.toFixed(1)} goles esperados</span>
      </div>
      <p class="meta pron__nota">marcador más probable según la simulación</p>
    </div>

    {#if pronostico.scorers.length}
      <div class="pron__anota card">
        <p class="pos-titulo">¿Quién anota? · prob. de marcar al menos un gol</p>
        <ul class="rows">
          {#each pronostico.scorers.slice(0, 6) as s (s.player_id)}
            <li class="anota-row">
              <span class="chip chip--{s.position}">{s.position}</span>
              <span class="anota-row__name">{s.player}</span>
              <span class="mini-barra anota-row__barra" style="--marcador: {Math.round(s.prob_score * 100)}">
                <span></span>
              </span>
              <span class="anota-row__num">{pct(s.prob_score)} · {s.goals_expected.toFixed(2)} E[⚽]</span>
            </li>
          {/each}
        </ul>
      </div>
    {:else}
      <div class="card centrado">
        <p class="meta">Sin proyecciones de anotadores todavía — se generan con los picks.</p>
      </div>
    {/if}
  </section>
{/if}
