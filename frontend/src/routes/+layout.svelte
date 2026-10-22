<script lang="ts">
  import "../app.css";
  const year = new Date().getFullYear();
  let { children } = $props();
</script>

<header>
  <div class="velocidad">
    <h1>⚽ PickMaster · Selecciona ya</h1>
    <p class="subtitulo">
      Picks con estadística, no con corazonadas. Frase del banquillo:
      “cada tiro a puerta lleva su porcentaje adjunto”.
    </p>
  </div>
</header>

<main>
  {@render children()}
</main>

<footer>
  <p>
    <strong>PickMaster</strong> ⚽ Liga MX · picks probabilísticos con simulación
    Monte Carlo · v0.2 · {year}
  </p>
  <p>
    <strong>No es asesoría financiera ni garantía de resultados.</strong> Solo
    para mayores de edad. Juega con responsabilidad — y recuerda: al modelo
    también le sacan golazos.
  </p>
</footer>

<style>
  main {
    max-width: 1080px;
    margin: 0 auto;
    padding: 1rem;
  }
  header {
    max-width: 1080px;
    margin: 1rem auto 0;
    padding: 0 1rem;
  }
</style>
