/**
 * Frases estilo anime de fútbol (originales, sin arte con copyright).
 * Humor ligado al tema: picks probabilísticos, simulaciones y porteros con guantes.
 */

export type Frase = {
  titulo: string;
  quote: string;
};

export const frasesCarga: Frase[] = [
  { titulo: "El portero calienta los guantes…", quote: "despejando las primeras líneas de bytes" },
  { titulo: "El DT gira la pizarra…", quote: "tácticas cuadradas, simulaciones al máximo" },
  { titulo: "Práctica al amanecer", quote: "el equipo corre 20 vueltas a la cancha antes del render" },
  { titulo: "Cámara lenta dramática", quote: "los datos van llegando a línea de meta" },
  { titulo: "Silencio en el vestuario…", quote: "el capitán traza la táctica con tiza" },
];

export const frasesVacio: Frase[] = [
  { titulo: "Cancha vacía", quote: "no hay picks todavía: ni las gradas tienen boletos" },
  { titulo: "¡DESAFÍO NULO!", quote: "esto pasa cuando nadie salta a la cancha" },
  { titulo: "Pitazo blanco", quote: "el juego aún no empieza" },
];

export const frasesError: Frase[] = [
  { titulo: "¡EL BALÓN SE DESVIÓ!", quote: "algo chocó en la red: reintentando el saque de banda" },
  { titulo: "El muro eterno", quote: "la defensa rival despejó nuestra petición" },
  { titulo: "Portero dormido", quote: "sé suave… el servidor se está estirando" },
  { titulo: "Fuera del campo", quote: "esto ya es falta directa: revisa tu conexión" },
];

export const frasesLineup: Frase[] = [
  { titulo: "Convocatoria en pizarra", quote: "ojo: NO es el XI confirmado; eso llega en T-1h" },
  { titulo: "¡Llegó la constancia!", quote: "convocatoria estimada del roster real" },
  { titulo: "Calentamiento completo", quote: "la alineación ya estiró ligamentos" },
];

export const frasesPicks: Frase[] = [
  { titulo: "Los más probables de la jornada", quote: "ordenados por simulación Monte Carlo, no por corazón" },
  { titulo: "Apuntado a la escuadra", quote: "cada tiro a puerta tiene su porcentaje" },
  { titulo: "Como dicen los abuelitos…", quote: "pocos datos, muchas ganas: cuidado con lo segundo" },
];

export const frasesProbables: Frase[] = [
  { titulo: "SELECCIÓN 5 ESTRELLAS", quote: "sólo entra quien supere el umbral de probabilidad" },
  { titulo: "La Súper Jugada (casi) segura", quote: "estadísticamente la más viable; nunca una garantía" },
  { titulo: "El cohete del banquillo", quote: "probabilidad arriba del umbral y con datos" },
];

export const mensajesGol: string[] = [
  "¡GOOOOL! La red explotó de puro análisis",
  "¡REMATE A LA ESCUADRA! Alta tensión dramática",
  "¡El despertar del balón! Secuencia de lanzamiento",
  "¡TIRO PODEROSO, YA! (con margen de error razonable)",
];

export const frasesEval: Frase[] = [
  { titulo: "El pitazo habla", quote: "resultados con luces muy distintas" },
  { titulo: "Hit rate humilde y honesto", quote: "aquí nadie promete trofeos, solo probabilidades" },
];

export const frasesPie: string[] = [
  "No es asesoría financiera ni garantía de resultados: juega con responsabilidad.",
  "El fútbol es incertidumbre pura: ni el mejor portero atrapa todos los soñados.",
  "Los datos orientan; el corazón hace fama… y a veces deudas.",
];

export function fraseAleatoria<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}
