import { SourceChip } from "@/components/shared/SourceInfo";
import { BookOpenCheck, ChevronDown } from "lucide-react";
import type { DecisionResult } from "@/types";

/**
 * Controlled, source-bound general statements (Law-Dossier, «Erlaubte Aussagen»).
 * Hidden when the case is outside the module (standard statements are suppressed).
 */
export function StatementsPanel({ decision }: { decision: DecisionResult }) {
  const statements = decision.approved_statements ?? [];

  if (decision.statements_suppressed) {
    return (
      <p role="note" className="rounded-md border border-line bg-sunken px-3.5 py-2.5 text-[12.5px] text-ink-muted">
        Dieser Fall liegt ausserhalb des Moduls. Es werden bewusst keine allgemeinen rechtlichen Hinweise angezeigt, weil sie hier nicht passen würden. Bitte eine Fachperson beiziehen.
      </p>
    );
  }
  if (statements.length === 0) return null;

  return (
    <details className="group rounded-lg border border-line bg-surface shadow-xs" data-testid="statements-panel">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-[13px] font-medium">
        <BookOpenCheck className="size-4 text-brand-600" aria-hidden />
        Rechtliche Hinweise zu diesem Fall ({statements.length})
        <span className="text-[12px] font-normal text-ink-subtle">freigegebene Aussagen, jeweils mit Quelle</span>
        <ChevronDown className="ml-auto size-4 text-ink-subtle transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <ul className="space-y-3 border-t border-line px-4 py-3">
        {statements.map((s) => (
          <li key={s.rule_id} className="text-[13px]">
            <p>{s.text_de}</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {s.source_ids.map((id) => (
                <SourceChip key={id} id={id} />
              ))}
            </div>
          </li>
        ))}
        <li className="text-[11.5px] text-ink-subtle">
          Allgemeine Informationen, keine Rechtsberatung und keine Aussage über die Gültigkeit der Kündigung oder
          ein Fristende. Die Beurteilung im Einzelfall übernimmt die Fachperson.
        </li>
      </ul>
    </details>
  );
}
