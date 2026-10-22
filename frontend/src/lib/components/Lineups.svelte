<script lang="ts">
  import Chibi from "$lib/components/Chibi.svelte";
  import { fraseAleatoria, frasesLineup, mensajesGol } from "$lib/phrases";

  type Props = {
    teams: Array<{
      team: string;
      kind: string;
      players: Array<{ id: number; name: string; position: string }>;
    }>;
  };
  let { teams }: Props = $props();

  const cabeza = fraseAleatoria(frasesLineup);
  const grito = fraseAleatoria(mensajesGol);
  const POSICIONES = ["GK", "DEF", "MID", "FWD"];
</script>

<section>
  <h2>🎓 Convocatorias: <span class="grito">{grito}</span></h2>
  <p class="subtitulo">{cabeza.titulo} — {cabeza.quote}</p>

  <div class="cols">
    {#each teams as t}
      <article>
        <h3>{t.team}</h3>
        <span class="meta">{"convocatoria "}{"estimada"}</span>
        {#each POSICIONES as pos}
          {@const enPos = t.players.filter((p) => p.position === pos)}
          {#if enPos.length}
            <h4>« {pos} ({enPos.length})»</h4>
            <ul class="chibis">
              {#each enPos as p (p.id)}
                <li title={p.name}>
                  <Chibi name={p.name} position={p.position} />
                  <span class="meta">
                    {p.name.replace(/^.*·/, "")}
                  </span>
                </li>
              {/each}
            </ul>
          {/if}
        {/each}
      </article>
    {/each}
  </div>
</section>

<style>
  .cols {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  }
  article {
    border: 2px solid var(--gold);
    border-radius: 14px;
    padding: 1rem;
    background: rgba(0, 0, 0, 0.25);
  }
  h3 { font-size: 1.1rem; margin-bottom: 0.3rem; }
  h4 { margin: 0.7rem 0 0.2rem; font-size: 0.85rem; }
  .chibis {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
    gap: 0.5rem;
  }
  .chibis li {
    display: grid;
    justify-items: center;
    font-size: 0.66rem;
    gap: 0.15rem;
  }
  .grito { color: var(--gold); font-size: 0.95rem; text-transform: none; }
</style>
