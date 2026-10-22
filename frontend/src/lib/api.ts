/** Cliente de la API de PickMaster. Browser: rutas relativas /api (proxy del edge). SSR: URL interna. */

import { browser } from "$app/environment";

let cachedBase: string | null = null;

async function base(): Promise<string> {
  if (cachedBase !== null) return cachedBase;
  if (browser) {
    cachedBase = "";
    return cachedBase;
  }
  // SSR: la URL difundida por el build/compose (p. ej. http://pickmaster-api:8000)
  let pub = "";
  try {
    const { env } = await import("$env/dynamic/public");
    pub = env.PUBLIC_API_URL ?? "";
  } catch {
    pub = "";
  }
  cachedBase = pub || "http://127.0.0.1:8000";
  return cachedBase;
}

export type Pick = {
  player_id: number;
  player: string;
  position: string;
  expected_points: number;
  target_points: number;
  probability: number;
  confidence: number;
  reason: string | null;
  value_per_salary?: number | null;
};

export type TopPick = Pick & {
  top_score: number;
  why: string[];
  gold_status: string;
  statistics?: {
    mean?: number | null;
    median?: number | null;
    p90?: number | null;
    minutes_expected?: number | null;
    start_probability?: number | null;
    confidence?: number | null;
    expected_events?: Record<string, number> | null;
  } | null;
};

export type Match = {
  id: number;
  home: string;
  away: string;
  kickoff: string;
  status: string;
  home_goals?: number | null;
  away_goals?: number | null;
};

export type Squad = {
  team: string;
  kind: string;
  players: Array<{ id: number; name: string; position: string }>;
};

export type Pronostico = {
  match_id: number;
  home: string;
  away: string;
  home_goals_expected: number;
  away_goals_expected: number;
  p_home: number;
  p_draw: number;
  p_away: number;
  most_likely_score: [number, number];
  scorers: Array<{
    player_id: number;
    player: string;
    position: string;
    team: string;
    goals_expected: number;
    prob_score: number;
  }>;
  disclaimer: string;
};

export type Proyeccion = {  player_id: number;
  match_id: number;
  model: string;
  mean: number;
  median: number;
  p10: number;
  p25: number;
  p75: number;
  p90: number;
  minutes_expected: number;
  start_probability: number;
  confidence: number;
  explanation?: string | null;
  expected_events?: Record<string, number> | null;
};



export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${await base()}${path}`);
  if (!res.ok) {
    throw new Error(`API ${path} → ${res.status}`);
  }
  return (await res.json()) as T;
}

export const api = {
  matches: () => get<{ matches: Match[] }>("/api/matches"),
  picks: (matchId: number) =>
    get<{ picks: Pick[] }>(`/api/picks?match_id=${matchId}`),
  topPicks: (matchId: number) =>
    get<{ top_picks: TopPick[] }>(`/api/picks/top?match_id=${matchId}`),
  lineups: (matchId: number) =>
    get<{ teams: Squad[] }>(`/api/lineups?match_id=${matchId}`),
  projection: (playerId: number, matchId: number) =>
    get<Proyeccion>(`/api/players/${playerId}/projection?match_id=${matchId}`),
  prediction: (matchId: number) =>
    get<Pronostico>(`/api/matches/${matchId}/prediction`),
};
