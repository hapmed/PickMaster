<script lang="ts">
  /** Convocatorias: chips compactos por posición (Apple-list-like). */
  import PlayerBadge from "$lib/components/PlayerBadge.svelte";

  type Props = {
    teams: Array<{
      team: string;
      kind: string;
      players: Array<{ id: number; name: string; position: string }>;
    }>;
  };
  let { teams }: Props = $props();

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
    <h2>Convocatorias</h2>
    <span class="section__tag">estimadas del roster · se confirman en T-1h</span>
  </div>

  {#if teams.length === 0}
    <div class="card centrado">
      <p class="meta">Convocatoria aún sin escoger en la pizarra.</p>
    </div>
  {:else}
    <div class="equipos">
      {#each teams as t (t.team)}
        <div class="card equipo">
          <h3>{t.team}</h3>
          <span class="meta">{t.kind === "confirmed" ? "alineación confirmada" : "convocatoria estimada"} · {t.players.length} jugadores</span>
          {#each POSICIONES as pos}
            {@const enPos = t.players.filter((p) => p.position === pos)}
            {#if enPos.length}
              <div class="pos-bloque">
                <p class="pos-titulo">{POS_NAMES[pos]} · {enPos.length}</p>
                <ul class="chips">
                  {#each enPos as p (p.id)}
                    <li title={p.name}>
                      <PlayerBadge name={p.name} position={p.position} />
                      <span>{p.name.replace(/^.*·/, "")}</span>
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
          {/each}
        </div>
      {/each}
    </div>
  {/if}
</section>
