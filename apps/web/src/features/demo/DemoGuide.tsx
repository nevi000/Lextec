import { Check, ChevronDown, FlaskConical, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import { useSystemStatus } from "@/lib/queries";
import { cn } from "@/lib/utils";
import type { MessageView } from "@/types";
import { DEMO_STEPS } from "./demoScenario";

/**
 * Dezente Demo-Hilfe. Fügt vorbereitete Texte in das normale Eingabefeld ein; die Analyse läuft danach
 * durch die echte Pipeline (Entscheidungs-Engine, Wissensbasis, ggf. Gemini). Nichts ist vorgetäuscht.
 */
export function DemoGuide({
  caseId,
  messages,
  draft,
  onInsert,
}: {
  caseId: string;
  messages: MessageView[];
  draft: string;
  onInsert: (text: string) => void;
}) {
  const { data: status } = useSystemStatus();
  const sent = new Set(messages.map((m) => m.content.trim()));
  const doneIds = DEMO_STEPS.filter((s) => s.text && sent.has(s.text.trim())).map((s) => s.id);
  const current = DEMO_STEPS.find((s) => s.text && !sent.has(s.text.trim()))?.id ?? 5;
  const gemini = status?.ai_is_external;

  return (
    <details open className="group rounded-lg border border-brand-200 bg-brand-50/60" data-testid="demo-guide">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3">
        <FlaskConical className="size-4 text-brand-700" aria-hidden />
        <span className="text-[13.5px] font-semibold">Geführte Demo: Mietkündigung Zürich</span>
        <Badge tone="warning">Synthetische Demo-Daten</Badge>
        <Badge tone={gemini ? "escalate" : "brand"}>{gemini ? `KI: Gemini (${status?.ai_model})` : "KI: Mock (simuliert)"}</Badge>
        <ChevronDown className="ml-auto size-4 text-ink-subtle transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-2 border-t border-brand-200/70 px-4 py-3">
        <p className="text-[12.5px] text-ink-muted">
          Die Beispielantworten laufen durch die normale Analyse. Sie können sie vorher bearbeiten oder frei eigene Texte
          eingeben.
          {gemini
            ? " Mit Gemini kann die Formulierung der Auswertung leicht abweichen; die Entscheidung bleibt regelbasiert."
            : " Im Mock-Modus erkennt eine einfache Stichwortlogik die Angaben. Mit Gemini versteht das System freie Formulierungen."}
        </p>
        <ol className="space-y-2">
          {DEMO_STEPS.map((step) => {
            const done = doneIds.includes(step.id);
            const active = step.id === current;
            const inserted = !!step.text && draft.trim() === step.text.trim();
            return (
              <li
                key={step.id}
                className={cn(
                  "rounded-md border bg-surface p-3",
                  active ? "border-brand-600 shadow-xs" : "border-line",
                  done && "opacity-70",
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "grid size-5 place-items-center rounded-full text-[11px] font-semibold",
                      done ? "bg-proceed-solid text-white" : active ? "bg-brand-900 text-white" : "bg-sunken text-ink-muted",
                    )}
                    aria-hidden
                  >
                    {done ? <Check className="size-3" /> : step.id}
                  </span>
                  <span className="text-[13px] font-medium">
                    Schritt {step.id} – {step.title}
                  </span>
                  {step.optional && <Badge tone="neutral">optional</Badge>}
                  {done && <Badge tone="proceed">erledigt</Badge>}
                </div>
                {step.text && active && (
                  <p className="mt-2 rounded-md bg-sunken px-2.5 py-2 text-[12.5px] italic text-ink-muted">«{step.text}»</p>
                )}
                {active && (
                  <>
                    <ul className="mt-2 list-disc space-y-0.5 pl-5 text-[12.5px] text-ink-muted">
                      {step.expect.map((e) => (
                        <li key={e}>{e}</li>
                      ))}
                    </ul>
                    <div className="mt-2.5">
                      {step.text ? (
                        <Button size="sm" variant={inserted ? "secondary" : "accent"} onClick={() => onInsert(step.text as string)}>
                          <ListChecks />
                          {inserted ? "Eingefügt – jetzt unten absenden" : "In Eingabefeld einfügen"}
                        </Button>
                      ) : (
                        <Button asChild size="sm" variant="accent">
                          <Link to={`/cases/${caseId}/briefing`}>Expert Briefing öffnen</Link>
                        </Button>
                      )}
                    </div>
                  </>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </details>
  );
}
