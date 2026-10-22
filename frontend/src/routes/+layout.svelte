<script lang="ts">
  import "../app.css";
  const year = new Date().getFullYear();
  let { children } = $props();
</script>

<header class="barra-superior">
  <div class="barra-superior__inner">
    <div class="brand">
      PickMaster <small>Liga MX · Apertura 2026-27</small>
    </div>
    <span class="meta">picks probabilísticos · Monte Carlo</span>
  </div>
</header>

<main class="page">
  {@render children()}
</main>

<footer>
  <p>
    <strong>PickMaster</strong> · v0.2 · {year} · Los picks son estimaciones
    estadísticas, no garantías.
  </p>
  <p>
    <strong>No es asesoría financiera ni garantía de resultados.</strong> Solo
    para mayores de edad. Juega con responsabilidad.
  </p>
</footer>
