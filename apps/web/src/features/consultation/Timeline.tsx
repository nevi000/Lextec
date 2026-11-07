import { ChevronDown, MessagesSquare, RefreshCw, Sparkles, UserRound } from "lucide-react";
import { ActionBadge, Badge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { displayValue, formatDateTime, parseServerDate } from "@/lib/utils";
import type { DecisionView, FactView, MessageView } from "@/types";

type Entry =
  | { kind: "message"; at: number; message: MessageView }
  | { kind: "decision"; at: number; decision: DecisionView };

export function Timeline({
  messages,
  decisions,
  facts,
  onRetry,
  retrying,
}: {
  messages: MessageView[];
  decisions: DecisionView[];
  facts: FactView[];
  onRetry: () => void;
  retrying: boolean;
}) {
  const entries: Entry[] = [
    ...messages.map((m) => ({ kind: "message" as const, at: parseServerDate(m.created_at).getTime(), message: m })),
    ...decisions.map((d) => ({ kind: "decision" as const, at: parseServerDate(d.created_at).getTime(), decision: d })),
  ].sort((a, b) => a.at - b.at);

  if (entries.length === 0) return null;
  const factLabel = (id: string | null) => facts.find((f) => f.fact_id === id)?.label_de ?? id;

  return (
    <details aria-label="Gesprächsverlauf" className="group rounded-lg border border-line bg-surface shadow-xs" data-testid="timeline">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-[13px] font-medium">
        <MessagesSquare className="size-4 text-brand-600" aria-hidden />
        Gesprächsverlauf anzeigen
        <span className="text-[12px] font-normal text-ink-subtle">{messages.length} Eintrag/Einträge</span>
        <ChevronDown className="ml-auto size-4 text-ink-subtle transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <ol className="space-y-3 border-t border-line p-4">
        {entries.map((e) =>
          e.kind === "message" ? (
            <li key={`m-${e.message.id}`} className="rounded-lg border border-line bg-surface p-3.5">
              <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[12px] text-ink-subtle">
                <UserRound className="size-3.5" aria-hidden />
                <span className="font-medium text-ink-muted">
                  {e.message.kind === "ANSWER"
                    ? `Antwort: ${factLabel(e.message.answers_fact_id)}`
                    : e.message.kind === "NOTE"
                      ? "Ergänzung"
                      : "Schilderung"}
                </span>
                <span>· {formatDateTime(e.message.created_at)}</span>
                {e.message.analysis_status === "FAILED" && <Badge tone="error">Analyse fehlgeschlagen</Badge>}
                {e.message.analysis_status === "PENDING" && <Badge tone="warning">Analyse ausstehend</Badge>}
              </div>
              <p className="whitespace-pre-wrap text-[14px] leading-relaxed">{e.message.content}</p>
              {e.message.analysis_status === "FAILED" && (
                <div className="mt-2 flex items-center gap-2 text-[12.5px] text-error-fg">
                  <span>{e.message.analysis_error}</span>
                  <Button size="sm" variant="secondary" loading={retrying} onClick={onRetry}>
                    <RefreshCw /> Erneut analysieren
                  </Button>
                </div>
              )}
              <ExtractedChips message={e.message} facts={facts} />
            </li>
          ) : (
            <li
              key={`d-${e.decision.id}`}
              className="flex flex-wrap items-center gap-2 rounded-md border border-dashed border-line-strong bg-sunken/60 px-3.5 py-2.5 text-[12.5px] text-ink-muted"
            >
              <Sparkles className="size-3.5 text-brand-600" aria-hidden />
              <span className="font-medium text-ink">Systemempfehlung</span>
              <ActionBadge action={e.decision.decision.action} />
              <span className="min-w-0 flex-1 basis-60">
                {decisionSummary(e.decision)}
              </span>
              <span className="text-ink-subtle">{formatDateTime(e.decision.created_at)}</span>
            </li>
          ),
        )}
      </ol>
    </details>
  );
}

function decisionSummary({ decision: d }: DecisionView): string {
  if (d.action === "ASK") return d.next_question?.question_de ?? d.explanation_de;
  if (d.action === "ESCALATE") return d.triggered_rules[0]?.reason_de ?? d.explanation_de;
  return "Alle erforderlichen Angaben liegen vor.";
}

function ExtractedChips({ message, facts }: { message: MessageView; facts: FactView[] }) {
  const mine = facts.filter((f) => f.source_message_id === message.id && (f.status === "KNOWN" || f.status === "AMBIGUOUS"));
  if (!mine.length) return null;
  return (
    <details className="mt-2.5 border-t border-line pt-2">
      <summary className="cursor-pointer text-[12px] font-medium text-brand-600 hover:underline">
        {mine.length} {message.kind === "ANSWER" ? "Angabe erfasst" : "Angaben erkannt (KI, noch nicht bestätigt)"}
      </summary>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {mine.map((f) => (
          <Badge key={f.fact_id} tone={f.status === "AMBIGUOUS" ? "ask" : "unverified"}>
            {f.label_de}: <strong className="font-semibold">{f.status === "AMBIGUOUS" ? "unklar" : displayValue(f.value)}</strong>
          </Badge>
        ))}
      </div>
    </details>
  );
}
