import { Check } from "lucide-react";
import { PHASES, type Phase } from "@/lib/caseStatus";
import { cn } from "@/lib/utils";

/** Orientation only: shows where the case stands. Nothing here blocks any action. */
export function PhaseStepper({ phase, questionsOpen = false }: { phase: Phase; questionsOpen?: boolean }) {
  return (
    <ol aria-label="Arbeitsschritte" className="no-print flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
      {PHASES.map((p, i) => {
        // «Fragen klären» is only marked done when nothing required is still open (no invented progress)
        const done = p.id < phase && !(p.id === 2 && questionsOpen);
        const current = p.id === phase;
        return (
          <li key={p.id} className="flex items-center gap-2" aria-current={current ? "step" : undefined}>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 border-b-2 py-1 font-medium",
                current ? "border-brand-600 text-ink" : "border-transparent",
                done && "text-brand-700",
                !current && !done && "text-ink-subtle",
              )}
            >
              {done ? <Check className="size-3.5" aria-label="abgeschlossen" /> : <span aria-hidden>{p.id}</span>}
              {p.label}
            </span>
            {i < PHASES.length - 1 && <span className="text-ink-subtle" aria-hidden>→</span>}
          </li>
        );
      })}
    </ol>
  );
}
