import { Check } from "lucide-react";
import { PHASES, type Phase } from "@/lib/caseStatus";
import { cn } from "@/lib/utils";

/** Orientation only: shows where the case stands. Nothing here blocks any action. */
export function PhaseStepper({ phase, questionsOpen = false }: { phase: Phase; questionsOpen?: boolean }) {
  return (
    <ol aria-label="Arbeitsschritte" className="no-print flex flex-wrap items-center gap-x-1.5 gap-y-2 text-[13px]">
      {PHASES.map((p, i) => {
        // «Fragen klären» is only marked done when nothing required is still open (no invented progress)
        const done = p.id < phase && !(p.id === 2 && questionsOpen);
        const current = p.id === phase;
        return (
          <li key={p.id} className="flex items-center gap-2" aria-current={current ? "step" : undefined}>
            <span
              className={cn(
                "inline-flex items-center gap-2 rounded-full py-1 pl-1 pr-3.5 text-[13.5px] font-medium transition-colors",
                current && "bg-brand-900 text-white shadow-xs",
                done && "text-brand-700",
                !current && !done && "text-ink-subtle",
              )}
            >
              <span
                className={cn(
                  "grid size-6 place-items-center rounded-full text-[12px] font-semibold",
                  current && "bg-white/15 text-white",
                  done && "bg-brand-100 text-brand-700",
                  !current && !done && "bg-sunken text-ink-subtle",
                )}
              >
                {done ? <Check className="size-3.5" aria-label="abgeschlossen" /> : <span aria-hidden>{p.id}</span>}
              </span>
              {p.label}
            </span>
            {i < PHASES.length - 1 && <span className="h-px w-5 bg-line-strong sm:w-8" aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}
