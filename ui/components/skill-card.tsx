import type { SkillCard as Skill } from "@/lib/api";

const STAGES = ["Static", "Security", "Injection", "Secret·PII", "Judge", "Verdict"];

// The verification badge is the centerpiece of every card: verdict pill + safety meter + the six
// scan-stage results. A skill with no passing scan_run + approval never reaches this component.
export function SkillCard({
  skill,
  safety,
  stages,
}: {
  skill: Skill;
  safety: number;
  stages: number[]; // per stage: 1 pass · 0 fail · 2 skipped
}) {
  const pct = Math.round(safety * 100);
  return (
    <article className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm">
      <header className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold leading-tight">{skill.name}</h3>
          <div className="font-mono text-xs text-muted-foreground">{skill.slug}</div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
          ✓ Verified
        </span>
      </header>

      <p className="text-sm text-muted-foreground">{skill.description}</p>

      <div className="flex flex-col gap-2 rounded-lg border bg-muted/40 p-3">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>
            Safety <b className="text-foreground">{safety.toFixed(2)}</b>
          </span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-border">
          <div className="h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
        </div>
        <div className="flex gap-1">
          {STAGES.map((s, i) => (
            <div key={s} className="flex-1 text-center">
              <div
                className={`h-1.5 rounded ${
                  stages[i] === 0 ? "bg-red-500" : stages[i] === 2 ? "bg-amber-500" : "bg-emerald-500"
                }`}
              />
              <small className="mt-1 block text-[9px] text-muted-foreground">{s}</small>
            </div>
          ))}
        </div>
      </div>

      <footer className="flex items-center gap-2">
        <code className="flex-1 truncate rounded bg-muted px-2 py-1 font-mono text-xs">{skill.install}</code>
      </footer>
    </article>
  );
}
