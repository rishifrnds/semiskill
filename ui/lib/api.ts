// Read-only client for the SemiSkill L3 read API (semiskill/api.py). NEVER writes the catalog —
// publishing stays behind the human-gated approval actuator (ADR-002). The caller's clearance is
// the X-Principal-Labels header; in production it derives from SharePoint SSO group membership.

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

async function get<T>(path: string, principal: string[]): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "X-Principal-Labels": principal.join(",") },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export function searchCatalog(
  principal: string[],
  q = "",
  facets: { function?: string; role?: string; level?: string } = {},
): Promise<SkillCard[]> {
  const params = new URLSearchParams({ q });
  for (const [k, v] of Object.entries(facets)) if (v) params.set(k, v);
  return get<{ results: SkillCard[] }>(`/catalog?${params}`, principal).then((r) => r.results);
}

export const getSkill = (id: string, principal: string[]) =>
  get<SkillCard & { verification: Verification | null }>(`/skill/${id}`, principal);

export const reviewQueue = (principal: string[]) =>
  get<{ queue: unknown[] }>(`/queue`, principal).then((r) => r.queue);
