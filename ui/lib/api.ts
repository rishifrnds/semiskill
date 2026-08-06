// Read-only client for the SemiSkill L3 read API (semiskill/api.py). NEVER writes the catalog —
// publishing stays behind the human-gated approval actuator (ADR-002). The browser never asserts
// permission labels; the API maps a verified Entra bearer identity to server-side entitlements.

const BASE = process.env.NEXT_PUBLIC_SEMISKILL_API ?? "http://127.0.0.1:8787";

export type SkillCard = {
  artifact_id: string;
  slug: string;
  name: string;
  description: string;
  version: string;
  function: string | null;
  role: string | null;
  level: string | null;
  install: string;
};

export type Verification = {
  verdict: string;
  aggregate_safety: number | null;
  stages: { stage: number; safety: number; hard_fail: boolean }[];
};

async function get<T>(path: string, accessToken?: string): Promise<T> {
  const headers: HeadersInit = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(`${BASE}${path}`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export function searchCatalog(
  q = "",
  facets: { function?: string; role?: string; level?: string } = {},
  accessToken?: string,
): Promise<SkillCard[]> {
  const params = new URLSearchParams({ q });
  for (const [k, v] of Object.entries(facets)) if (v) params.set(k, v);
  return get<{ results: SkillCard[] }>(`/catalog?${params}`, accessToken).then((r) => r.results);
}

export const getSkill = (id: string, accessToken?: string) =>
  get<SkillCard & { verification: Verification | null }>(`/skill/${id}`, accessToken);

export const reviewQueue = (accessToken: string) =>
  get<{ queue: unknown[] }>(`/queue`, accessToken).then((r) => r.queue);
