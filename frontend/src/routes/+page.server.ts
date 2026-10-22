/** Carga en SSR: próximos partidos + picks + top picks + alineaciones (con degradación amable). */
import { api } from "$lib/api";
import { fraseAleatoria, frasesError, frasesVacio } from "$lib/phrases";

export async function load({ url }) {
  try {
    const { matches } = await api.matches();
    const proximos = matches.filter((m) => m.status === "scheduled");
    const elegido =
      Number(url.searchParams.get("partido")) || proximos[0]?.id || matches[0]?.id;
    if (!elegido) {
      return { estado: "vacio", frase: fraseAleatoria(frasesVacio) };
    }
    const [picks, top, lineups] = await Promise.all([
      api.picks(elegido),
      api.topPicks(elegido),
      api.lineups(elegido),
    ]);
    return {
      estado: "ok",
      partidoId: elegido,
      matches,
      picks: picks.picks,
      top: top.top_picks,
      teams: lineups.teams,
    };
  } catch {
    return { estado: "error", frase: fraseAleatoria(frasesError) };
  }
}
