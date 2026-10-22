<script lang="ts">
  /**
   * Insignia de jugador: camiseta plana estilo fantasy (limpia, número grande).
   * Determinista por nombre; colores por posición al estilo Apple HIG.
   */
  type Props = {
    name: string;
    position: string;
    gold?: boolean;
    numero?: number;
  };

  let { name, position, gold = false, numero }: Props = $props();

  function hash(texto: string): number {
    let h = 0;
    for (const c of texto) {
      h = (h * 31 + c.charCodeAt(0)) >>> 0;
    }
    return h;
  }

  const h = $derived(hash(`${name}|${position}`));
  const numeroCamiseta = $derived(numero ?? ((h >>> 5) % 30) + 1);

  const JERSEYS: Record<string, string> = {
    GK: "#b45309",
    DEF: "#1d4ed8",
    MID: "#15803d",
    FWD: "#dc2626",
    default: "#8e8e93",
  };
  const color = $derived(JERSEYS[position] ?? JERSEYS.default);
</script>

<svg
  viewBox="0 0 64 64"
  role="img"
  aria-label={`camiseta de ${name}`}
  style="width:var(--badge-w, 100%);height:auto;display:block"
>
  {#if gold}
    <circle cx="32" cy="34" r="27" fill="none" stroke="var(--gold, #8f6a00)" stroke-width="2.5" opacity="0.85" />
  {/if}

  <path
    d="M 22 12 L 10 18 L 14 27 L 21 25 L 21 52 Q 32 56 43 52 L 43 25 L 50 27 L 54 18 L 42 12 Q 37 18 32 18 Q 27 18 22 12 Z"
    fill={color}
  />
  <text
    x="32"
    y="46"
    text-anchor="middle"
    font-size="18"
    font-weight="700"
    fill="#ffffff"
  >
    {numeroCamiseta}
  </text>

  <title>{name}</title>
</svg>
