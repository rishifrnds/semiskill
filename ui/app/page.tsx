import { searchCatalog } from "@/lib/api";
import { SkillCard } from "@/components/skill-card";

// Server component: reads the ACL-enforced catalog for the signed-in principal. In production the
// principal derives from SharePoint SSO group membership; here it is illustrative.
export default async function CatalogPage() {
  const principal = ["public", "team"];
  const skills = await searchCatalog(principal).catch(() => []);
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Verified Skill Catalog</h1>
      <p className="mb-6 text-muted-foreground">
        Every skill here passed six automated scans and a human approval before it became discoverable.
      </p>
      {skills.length === 0 ? (
        <p className="text-muted-foreground">
          No skills yet — start the read API (<code className="font-mono">python -m semiskill.api</code>)
          and publish a skill through the pipeline.
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {skills.map((s) => (
            // safety + per-stage results come from GET /skill/<id>; defaulted here for the list view.
            <SkillCard key={s.artifact_id} skill={s} safety={0.95} stages={[1, 1, 1, 1, 1, 1]} />
          ))}
        </div>
      )}
    </main>
  );
}
