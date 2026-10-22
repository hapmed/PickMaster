/** Cliente de la API de PickMaster (base URL configurable via PUBLIC_API_URL). */

import { env } from "$env/dynamic/public";

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

export type ChibiTeam = {
  team: string;
  kind: string;
  players: Array<{ id: number; name: string; position: string }>;
};

const BASE: string = env.PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
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
    get<{ teams: ChibiTeam[] }>(`/api/lineups?match_id=${matchId}`),
};
