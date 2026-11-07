import { ChevronRight, Scale } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ActionBadge, Badge, FactStatusBadge, ProvenanceBadge } from "@/components/shared/badges";
import { SectionLabel } from "@/components/shared/states";
import { displayValue } from "@/lib/utils";
import type { CaseDetail, FactView } from "@/types";

function FactRow({ fact, onOpen }: { fact: FactView; onOpen: () => void }) {
  const known = fact.status === "KNOWN";
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="group flex w-full items-start gap-2 rounded-md px-2 py-2 text-left hover:bg-brand-50"
        aria-label={`${fact.label_de}: ${known ? displayValue(fact.value) : fact.status}. Details öffnen`}
      >
        <div className="min-w-0 flex-1">
          <div className="text-[12.5px] text-ink-muted">
            {fact.label_de}
            {fact.deferred_reason && <span className="ml-1.5 text-ask-fg">· zurückgestellt</span>}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
            {known ? (
              <span className="text-[13.5px] font-medium">
                {fact.enum_labels_de?.[String(fact.value)] ?? displayValue(fact.value)}
              </span>
            ) : (
              <FactStatusBadge status={fact.status} />
            )}
            {known && <ProvenanceBadge origin={fact.origin} confirmed={fact.confirmed} />}
            {known && fact.documented && <Badge tone="proceed">Dokumentarisch belegt</Badge>}
          </div>
        </div>
        <ChevronRight className="mt-1.5 size-3.5 shrink-0 text-ink-subtle opacity-0 group-hover:opacity-100" aria-hidden />
      </button>
    </li>
  );
}

function Group({
  title,
  facts,
  onOpen,
  tone,
}: {
  title: string;
  facts: FactView[];
  onOpen: (f: FactView) => void;
  tone?: "ask" | "escalate" | "incomplete";
}) {
  if (!facts.length) return null;
  return (
    <div className="mt-4">
      <div className="mb-1 flex items-center gap-2 px-2">
        <SectionLabel>{title}</SectionLabel>
        <Badge tone={tone ?? "neutral"}>{facts.length}</Badge>
      </div>
      <ul>
        {facts.map((f) => (
          <FactRow key={f.fact_id} fact={f} onOpen={() => onOpen(f)} />
        ))}
      </ul>
    </div>
  );
}

export function CasePanel({
  detail,
  facts,
  onOpenFact,
}: {
  detail: CaseDetail;
  facts: FactView[];
  onOpenFact: (f: FactView) => void;
}) {
  const [showOptional, setShowOptional] = useState(false);
  const decision = detail.current_decision;
  const known = facts.filter((f) => f.status === "KNOWN" || f.status === "NOT_APPLICABLE");
  const unclear = facts.filter((f) => f.status === "AMBIGUOUS" || f.status === "CONTRADICTORY");
  const open = facts.filter((f) => f.status === "MISSING" && f.required);
  const unknownAsked = facts.filter((f) => f.status === "UNKNOWN");
  const optional = facts.filter((f) => f.status === "MISSING" && !f.required);
  const contradictory = facts.filter((f) => f.status === "CONTRADICTORY");

  return (
    <div aria-label="Fallverständnis" role="region">
      <SectionLabel>Erkannte Rechtsgebiete</SectionLabel>
      {detail.issues.length === 0 ? (
        <p className="mt-2 text-[13px] text-ink-subtle">Noch keine erkannt.</p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {detail.issues.map((i) => (
            <li key={i.id} className="flex items-center justify-between gap-2 text-[13px]">
              <span className="flex items-center gap-1.5 font-medium">
                <Scale className="size-3.5 text-brand-600" aria-hidden />
                {i.title_de ?? i.description}
              </span>
              {i.classification_status === "UNSUPPORTED" && <Badge tone="escalate">Nicht abgedeckt</Badge>}
            </li>
          ))}
        </ul>
      )}

      {detail.summary && (
        <p className="mt-3 rounded-md bg-sunken p-2.5 text-[12.5px] text-ink-muted">
          <span className="font-medium text-ink">Zusammenfassung (KI): </span>
          {detail.summary}
        </p>
      )}

      <div className="mt-5 flex items-center justify-between border-t border-line pt-4">
        <SectionLabel>Aktuelle Einschätzung</SectionLabel>
        <ActionBadge action={decision?.action} />
      </div>
      {decision && (
        <p className="mt-1.5 text-[12px] text-ink-subtle">
          <Link to={`/cases/${detail.id}/decision`} className="font-medium text-brand-600 hover:underline">
            Begründung ansehen
          </Link>
          {decision.main_reason_code && <span className="ml-2 font-mono text-ink-subtle">{decision.main_reason_code}</span>}
        </p>
      )}

      {contradictory.length > 0 && (
        <p role="status" className="mt-3 rounded-md bg-escalate-bg p-2.5 text-[12.5px] text-escalate-fg">
          {contradictory.length} widersprüchliche Angabe(n) – bitte klären.
        </p>
      )}

      <div className="mt-5 border-t border-line pt-1">
        <Group title="Unklar / widersprüchlich" facts={unclear} onOpen={onOpenFact} tone="escalate" />
        <Group title="Offen (noch nicht gefragt)" facts={open} onOpen={onOpenFact} tone="incomplete" />
        <Group title="Gefragt, unbekannt" facts={unknownAsked} onOpen={onOpenFact} tone="ask" />
        <Group title="Bekannt" facts={known} onOpen={onOpenFact} />
        {optional.length > 0 && (
          <div className="mt-4">
            <button
              type="button"
              className="px-2 text-[12px] font-medium text-brand-600 hover:underline"
              onClick={() => setShowOptional((s) => !s)}
              aria-expanded={showOptional}
            >
              {showOptional ? "Optionale Angaben ausblenden" : `${optional.length} optionale Angabe(n) anzeigen`}
            </button>
            {showOptional && (
              <ul className="mt-1">
                {optional.map((f) => (
                  <FactRow key={f.fact_id} fact={f} onOpen={() => onOpenFact(f)} />
                ))}
              </ul>
            )}
          </div>
        )}
        {facts.length === 0 && <p className="mt-4 px-2 text-[13px] text-ink-subtle">Noch keine Angaben erfasst.</p>}
      </div>
    </div>
  );
}
