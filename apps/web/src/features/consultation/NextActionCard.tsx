import { MessageCircleQuestionMark } from "lucide-react";
import { Badge } from "@/components/shared/badges";
import { cn } from "@/lib/utils";
import type { CaseDetail, DecisionResult } from "@/types";
import { NextSteps } from "./NextSteps";
import { QuestionForm } from "./QuestionForm";

export interface Props {
  detail: CaseDetail;
  decision: DecisionResult;
  busy: boolean;
  hasBriefing: boolean;
  briefingStale: boolean;
  briefingError: string | null;
  onOpenMore: () => void;
  onAnswer: (factId: string, text: string) => void;
  onUnknown: (factId: string) => void;
  onDefer: (factId: string, label: string) => void;
  onSkip: (factId: string) => void;
  onRequestHandover: () => void;
  onCompleteHandover: () => void;
  onCreateBriefing: () => void;
  briefingBusy: boolean;
}

const shell = "print-break-avoid rounded-xl border p-5 shadow-card sm:p-7";

export function NextActionCard(p: Props) {
  if (p.decision.action === "ASK") return <AskCard {...p} />;
  return <NextSteps {...p} />;
}

/** Phase 2: exactly one prominent question. */
function AskCard({ detail, decision, busy, onAnswer, onUnknown, onDefer, onSkip }: Props) {
  const q = decision.next_question;
  const closed = detail.status === "CLOSED";
  return (
    <section aria-label="Nächste empfohlene Aktion" className={cn(shell, "border-brand-600/25 bg-surface shadow-raised")}>
      <header className="mb-4 flex items-center gap-2.5">
        <Badge tone="brand" icon={MessageCircleQuestionMark}>
          Nächste Frage
        </Badge>
        {decision.missing_facts.length > 1 && (
          <span className="text-[12.5px] text-ink-subtle" title={`${decision.missing_facts.length} Angaben sind noch offen`}>
            Eine Frage nach der anderen
            <span className="sr-only"> ({decision.missing_facts.length} Angaben noch offen)</span>
          </span>
        )}
      </header>
      <h2 className="sr-only">Nächste empfohlene Aktion</h2>
      {q && q.fact_id ? (
        <QuestionForm
          key={q.fact_id}
          question={q}
          busy={busy}
          disabled={closed}
          optionalMode={q.optional}
          onAnswer={(t) => onAnswer(q.fact_id as string, t)}
          onUnknown={() => onUnknown(q.fact_id as string)}
          onDefer={() => (q.optional ? onSkip(q.fact_id as string) : onDefer(q.fact_id as string, q.question_de))}
        />
      ) : (
        <p className="text-[17px] font-semibold leading-snug">{q?.question_de ?? "Bitte schildern Sie die Situation."}</p>
      )}
    </section>
  );
}

