<script lang="ts">
  /**
   * Chibi anime de fútbol generado por código (SVG, determinista por nombre).
   * Cabeza grande, ojos brillantes, peinado exagerado y camiseta con los colores
   * del equipo. Sin imágenes externas: todo dibujado con formas.
   */
  type Props = {
    name: string;
    position: string;
    gold?: boolean;
    numero?: number;
  };

  let { name, position, gold = false, numero }: Props = $props();

  const HAIRCUTS = ["puntas", "poni", "cabeza"];
  const HAIRCUTS_SVG: Record<string, string> = {
    puntas: "M 12 16 L 20 4 L 24 12 L 32 2 L 40 12 L 44 4 L 52 16 Q 32 8 12 16 Z",
    poni: "M 10 18 Q 14 2 32 2 Q 50 2 54 18 Q 40 10 32 12 Q 24 10 10 18 Z",
    cabeza: "M 12 18 Q 18 6 32 6 Q 46 6 52 18 Q 40 12 32 13 Q 24 12 12 18 Z",
  };

  const HAIR_COLORS = ["#22223b", "#7f5539", "#e0b354", "#9f1119", "#1b4332", "#3a86ff", "#6a0dad"];
  const SKIN = "#ffd9b3";

  function hash(texto: string): number {
    let h = 0;
    for (const c of texto) {
      h = (h * 31 + c.charCodeAt(0)) >>> 0;
    }
    return h;
  }

  const h = $derived(hash(`${name}|${position}`));
  const corte = $derived(HAIRCUTS[h % HAIRCUTS.length]);
  const pelo = $derived(HAIR_COLORS[(h >> 3) % HAIR_COLORS.length]);
  const numeroChibi = $derived(numero ?? ((h >>> 5) % 90) + 1);

  const KIT_COLORS: Record<string, { camiseta: string; franja: string }> = {
    default: { camiseta: "#e8e8e8", franja: "#222" },
    GK: { camiseta: "#f59e0b", franja: "#fff" },
    DEF: { camiseta: "#2563eb", franja: "#ddd" },
    MID: { camiseta: "#16a34a", franja: "#f5f5f5" },
    FWD: { camiseta: "#dc2626", franja: "#ffe066" },
  };
  const kit = $derived(KIT_COLORS[position] ?? KIT_COLORS.default);
</script>

<svg
  viewBox="0 0 64 64"
  role="img"
  aria-label={`chibi de ${name}`}
  class="chibi"
  style="width:100%;height:auto"
>
  <defs>
    <radialGradient id={`aura-${h}`} cx="50%" cy="50%" r="55%">
      <stop offset="70%" stop-color="rgba(255,207,0,0)" />
      <stop offset="100%" stop-color={gold ? "rgba(255,207,0,0.55)" : "rgba(125,211,252,0.25)"} />
    </radialGradient>
  </defs>

  {#if gold}
    <circle cx="32" cy="30" r="30" fill={`url(#aura-${h})`} />
  {/if}

  <!-- cuerpo / camiseta -->
  <path
    d="M 14 64 Q 14 44 32 42 Q 50 44 50 64 Z"
    fill={kit.camiseta}
    stroke="rgba(0,0,0,0.35)"
    stroke-width="1.4"
  />
  <path d="M 32 43 Q 36 48 32 63" stroke={kit.franja} stroke-width="3" fill="none" />
  <text x="32" y="58" text-anchor="middle" font-size="9" font-weight="bold" fill="#101010">
    {numeroChibi}
  </text>

  <!-- cabeza chibi (grande) -->
  <circle cx="32" cy="24" r="16" fill={SKIN} stroke="rgba(0,0,0,0.35)" stroke-width="1.4" />
  <path d={HAIRCUTS_SVG[corte]} fill={pelo} stroke="rgba(0,0,0,0.4)" stroke-width="1.1" />

  <!-- ojos anime brillantes -->
  <ellipse cx="26" cy="26" rx="3.4" ry="4.6" fill="#fff" />
  <ellipse cx="38" cy="26" rx="3.4" ry="4.6" fill="#fff" />
  <circle cx="26" cy="27" r="2" fill="#10b981" />
  <circle cx="38" cy="27" r="2" fill="#10b981" />
  <circle cx="25" cy="24.6" r="0.9" fill="#ffffff" />
  <circle cx="37" cy="24.6" r="0.9" fill="#ffffff" />

  <!-- boca y mejillas -->
  <path d="M 29 34 Q 32 36.4 35 34" stroke="#a1431c" stroke-width="1.3" fill="none" />
  <circle cx="20" cy="31" r="2" fill="#fda4af" opacity="0.75" />
  <circle cx="44" cy="31" r="2" fill="#fda4af" opacity="0.75" />

  <title>{name}</title>
</svg>

<style>
  .chibi {
    display: block;
    filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.45));
  }
</style>
