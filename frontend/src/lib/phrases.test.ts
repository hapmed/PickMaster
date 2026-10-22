import { describe, expect, it, test } from "vitest";
import { fraseAleatoria, frasesCarga, mensajesGol, frasesError } from "./phrases";

describe("frases", () => {
  it("frasesCarga no vacía y con ambos campos", () => {
    expect(frasesCarga.length).toBeGreaterThan(0);
    for (const f of frasesCarga) {
      expect(f.titulo.length).toBeGreaterThan(0);
      expect(f.quote.length).toBeGreaterThan(0);
    }
  });

  it("fraseAleatoria siempre devuelve elemento de la lista", () => {
    for (let i = 0; i < 30; i++) {
      const f = fraseAleatoria(frasesCarga);
      expect(frasesCarga).toContain(f);
    }
  });

  it("mensajesGol existe con español limpio (sin vocales enmangadas)", () => {
    expect(mensajesGol.some((m) => m.startsWith("¡GOOOOL!"))).toBe(true);
    expect(frasesError.length).toBeGreaterThan(2);
  });

  test.todo("futuro: fixture del componente TopPicks con insignias");
});
