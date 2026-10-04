import { Confidence } from "@/components/ui/confidence";
import { PriorityTag } from "@/components/ui/priority";
import type { Evidence, Recommendation } from "@/lib/types";
import { EvidenceList } from "./evidence-chip";

const SECTIONS: { title: string; areas: Recommendation["area"][]; blurb: string }[] = [
  { title: "Reliability", areas: ["reliability", "security", "observability"], blurb: "Evals, security boundaries and observability this application is missing." },
  { title: "Inference", areas: ["inference"], blurb: "Serving, prompt-shape and workload findings, with how to measure them." },
  { title: "Application", areas: ["application"], blurb: "" },
];

/** Render inline `code` spans in rule text. */
function Rich({ text }: { text: string }) {
  const parts = text.split(/(`[^`]+`)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("`") && p.endsWith("`") ? (
          <code key={i} className="num rounded-[2px] bg-bg-3 px-1 text-[12px] text-fg-0">
            {p.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

function Row({ r, evidence }: { r: Recommendation; evidence: Record<string, Evidence> }) {
  return (
    <li className="grid grid-cols-[auto_1fr] gap-x-4 border-t border-line py-5 first:border-t-0">
      <div className="pt-0.5">
        <PriorityTag p={r.priority} />
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h3 className="text-[14px] font-medium text-fg-0">
            <Rich text={r.title} />
          </h3>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-fg-3">{r.area}</span>
            <Confidence value={r.confidence} />
          </div>
        </div>
        <p className="mt-1.5 max-w-[760px] text-[13px] leading-relaxed text-fg-1">
          <Rich text={r.why} />
        </p>
        <p className="mt-2 max-w-[760px] text-[12px] leading-relaxed text-fg-2">
          <span className="text-fg-3">Verify · </span>
          <Rich text={r.verification_method} />
        </p>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <EvidenceList ids={r.evidence_ids} evidence={evidence} />
          {r.forge_action && <span className="num mt-2 text-[11px] text-fg-3">Forge can install</span>}
        </div>
      </div>
    </li>
  );
}

export function Recommendations({ recs, evidence }: { recs: Recommendation[]; evidence: Record<string, Evidence> }) {
  return (
    <div className="space-y-10">
      {SECTIONS.map((s) => {
        const items = recs.filter((r) => s.areas.includes(r.area));
        if (!items.length) return null;
        return (
          <section key={s.title}>
            <div className="flex items-baseline justify-between border-b border-line-strong pb-2">
              <h2 className="font-display text-[18px] font-semibold tracking-[-0.01em]">{s.title}</h2>
              <span className="num text-[12px] text-fg-3">
                {items.length} finding{items.length === 1 ? "" : "s"}
              </span>
            </div>
            {s.blurb && <p className="mt-2 text-[12px] text-fg-3">{s.blurb}</p>}
            <ul>
              {items.map((r) => (
                <Row key={r.id} r={r} evidence={evidence} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
