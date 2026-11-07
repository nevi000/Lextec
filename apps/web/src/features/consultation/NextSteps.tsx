import { ChevronDown, Clock3, Download, FileText, TriangleAlert } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Badge, URGENCY_LABEL } from "@/components/shared/badges";
import { OrgCard } from "@/components/shared/OrgCard";
import { Button } from "@/components/ui/button";
import { useProfessionals } from "@/lib/queries";
import { cn } from "@/lib/utils";
import type { MissingFact, NextQuestion } from "@/types";
import type { Props } from "./NextActionCard";
import { QuestionForm } from "./QuestionForm";

const URGENCY_RANK: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };

function Section({ title, children, accent }: { title: string; children: ReactNode; accent?: string }) {
  return (
    <section
      aria-label={title}
      className={cn("print-break-avoid rounded-lg border border-line bg-surface p-5 shadow-card sm:p-6", accent && `border-l-4 ${accent}`)}
    >
      {children}
    </section>
  );
}

const h2 = "text-[18px] font-semibold leading-snug";

/**
 * Phase 3 in three clearly separated areas:
 *  A) assessment and next action (backend decision, calm colours, red only when urgent)
 *  B1) «Fallaufnahme vervollständigen»: important open facts, one question at a time, never blocking the handover
 *  B2) optional supplementary questions (opt-in, one at a time, never blocking)
 *  C) case report (the single primary action) + separate handover status
 */
export function NextSteps(p: Props) {
  return (
    <div role="region" aria-label="Nächste empfohlene Aktion" className="space-y-4">
      <Assessment {...p} />
      <Intake {...p} />
      <Supplement {...p} />
      <Report {...p} />
    </div>
  );
}

/* ----------------------------------------------------------------------------------- A */
function Assessment({ detail, decision }: Props) {
  const { label: proLabel } = useProfessionals();
  const escalate = decision.action === "ESCALATE";
  const urgent = decision.max_urgency === "HIGH";
  const rules = [...decision.triggered_rules].sort((a, b) => (URGENCY_RANK[b.urgency] ?? 0) - (URGENCY_RANK[a.urgency] ?? 0));
  const professionals = decision.recommended_professionals.map(proLabel);
  const urgencyLabel = decision.max_urgency ? URGENCY_LABEL[decision.max_urgency] : null;
  const issueTitle = (id: string | null | undefined) => detail.issues.find((i) => i.issue_definition_id === id)?.title_de ?? id ?? "";

  return (
    <Section
      title="Einschätzung"
      accent={escalate ? (urgent ? "border-l-escalate-solid" : "border-l-ask-solid") : "border-l-brand-500"}
    >
      {urgent && (
        <div role="alert" className="mb-4 flex items-start gap-2.5 rounded-md border border-escalate-line bg-escalate-bg px-3.5 py-3 text-[13.5px] text-escalate-fg">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>
            <strong>Dringend.</strong> Bitte nehmen Sie umgehend Kontakt mit einer geeigneten Fachperson auf. Ein Fallbericht
            ersetzt diese Kontaktaufnahme nicht.
          </p>
        </div>
      )}
      <p className="text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Was empfiehlt LexTec Bridge?</p>
      <h2 className={cn(h2, "mt-1")}>
        {escalate ? (urgent ? "Dringende Prüfung durch eine Fachperson empfohlen" : "Prüfung durch eine Fachperson empfohlen") : "Der Fall kann weiter bearbeitet werden"}
      </h2>
      {escalate ? (
        <>
          <p className="mt-1.5 text-[13.5px] text-ink-muted">
            Bei diesem Fall gibt es Fragen, die eine Fachperson prüfen sollte. LexTec Bridge gibt keine Rechtsauskunft.
          </p>
          {rules.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-[14px]">
              {rules.slice(0, 2).map((r) => (
                <li key={r.rule_id}>{r.reason_de}</li>
              ))}
            </ul>
          )}
          {(decision.referrals?.primary.length ?? 0) > 0 ? (
            <div className="mt-4" data-testid="referrals">
              <p className="text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Empfohlene Anlaufstellen</p>
              <ul className="mt-2 grid gap-3">
                {decision.referrals!.primary.map((o) => (
                  <li key={o.id}>
                    <OrgCard org={o} />
                  </li>
                ))}
              </ul>
              {(decision.referrals!.more.length > 0 || decision.referrals!.notes_de.length > 0) && (
                <details className="group mt-3">
                  <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[12.5px] font-medium text-brand-700 hover:underline">
                    <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
                    Weitere Anlaufstellen ({decision.referrals!.more.length})
                  </summary>
                  <ul className="mt-2 grid gap-3">
                    {decision.referrals!.more.map((o) => (
                      <li key={o.id}>
                        <OrgCard org={o} />
                      </li>
                    ))}
                  </ul>
                  {decision.referrals!.notes_de.map((n) => (
                    <p key={n} className="mt-2 text-[12px] text-ink-subtle">
                      {n}
                    </p>
                  ))}
                </details>
              )}
              {decision.referrals!.location_de && (
                <p className="mt-2 text-[12px] text-ink-subtle">Zuordnung nach: {decision.referrals!.location_de}</p>
              )}
            </div>
          ) : null}
          <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13.5px]">
            {professionals.length > 0 && (
              <span>
                <span className="text-ink-subtle">Empfohlene Fachperson: </span>
                {professionals.map((l, i) => (
                  <span key={l}>
                    {i > 0 && ", "}
                    <strong className="font-semibold">{l}</strong>
                  </span>
                ))}
              </span>
            )}
            {urgencyLabel && (
              <span className="inline-flex items-center gap-1 text-ink-muted">
                <Clock3 className="size-3.5" aria-hidden /> Dringlichkeit: {urgencyLabel}
              </span>
            )}
          </p>
        </>
      ) : (
        <p className="mt-1.5 text-[13.5px] text-ink-muted">
          Alle erforderlichen Angaben liegen vor. Das ist keine verbindliche Rechtsauskunft.
        </p>
      )}

      <details className="group mt-4 border-t border-line pt-3">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[12.5px] font-medium text-brand-700 hover:underline">
          <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
          Rechtliche Details ansehen
        </summary>
        <div className="mt-3 space-y-3" data-testid="decision-details">
          {rules.length > 0 && (
            <ul className="space-y-2">
              {rules.map((r) => (
                <li key={r.rule_id} className="rounded-md border border-line bg-canvas p-3">
                  <p className="text-[13.5px]">{r.reason_de}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11.5px]">
                    <Badge tone="neutral">
                      Regel <span className="font-mono">{r.rule_id}</span>
                    </Badge>
                    <Badge tone="neutral">
                      Code <span className="font-mono">{r.reason_code}</span>
                    </Badge>
                    {r.issue_id && <Badge tone="brand">{issueTitle(r.issue_id)}</Badge>}
                    <Badge tone={r.urgency === "HIGH" ? "escalate" : "neutral"}>Dringlichkeit: {r.urgency_label_de}</Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {(decision.related_routes ?? []).length > 0 && (
            <div className="rounded-md border border-line bg-canvas p-3 text-[13px]">
              <p className="text-[11.5px] font-semibold uppercase tracking-wide text-ink-subtle">Verweis auf andere Issues</p>
              <ul className="mt-1.5 space-y-1.5">
                {(decision.related_routes ?? []).map((r) => (
                  <li key={r.issue_id}>
                    <strong>{r.title_de}</strong>{" "}
                    <Badge tone={r.available ? "proceed" : "incomplete"}>{r.available ? "Dossierstand, nicht freigegeben" : "noch nicht verfügbar"}</Badge>
                    <p className="mt-0.5 text-ink-muted">{r.note_de}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-[12px] text-ink-subtle">
            Hauptgrund <span className="font-mono">{decision.main_reason_code}</span> ·{" "}
            <Link to={`/cases/${detail.id}/decision`} className="font-medium text-brand-700 hover:underline">
              Vollständige Entscheidungsbegründung
            </Link>
          </p>
        </div>
      </details>
    </Section>
  );
}

/** A backend MissingFact in the shape the question form expects. */
function asQuestion(m: MissingFact, optional: boolean): NextQuestion {
  return {
    fact_id: m.fact_id,
    question_de: m.question_de,
    why_needed_de: m.why_needed_de,
    data_type: m.data_type,
    enum_values: m.enum_values,
    enum_labels_de: m.enum_labels_de,
    deferred: m.deferred,
    optional,
  } as NextQuestion;
}

/* ----------------------------------------------------------------------------------- B1 */
/**
 * An escalation means human help is needed, NOT that the intake is over. Important open facts (required /
 * conditionally required, from the knowledge base) stay askable, one at a time. Nothing here blocks the report
 * or the handover; for urgent cases the contact recommendation above stays the main action.
 */
function Intake({ decision, detail, busy, onAnswer, onUnknown, onDefer }: Props) {
  const closed = detail.status === "CLOSED";
  const urgent = decision.max_urgency === "HIGH";
  const open = decision.missing_facts.filter((m) => !m.deferred);
  const n = decision.intake?.important_open ?? open.length;
  const first = open[0];
  const q = first ? asQuestion(first, false) : null;
  if (decision.action !== "ESCALATE") return null;

  return (
    <Section title="Fallaufnahme vervollständigen">
      <h2 className={h2}>Fallaufnahme vervollständigen</h2>
      {q ? (
        <>
          <p className="mt-1 text-[13.5px] text-ink-muted">
            <strong className="font-semibold text-ink">{n === 1 ? "Noch 1 wichtige Angabe offen." : `Noch ${n} wichtige Angaben offen.`}</strong>{" "}
            Diese Informationen helfen der Fachperson bei der Prüfung.{" "}
            {urgent
              ? "Sie können parallel ergänzen. Die Kontaktaufnahme mit der Fachperson muss nicht warten."
              : "Sie können den Fallbericht jederzeit erstellen, auch wenn noch Fragen offen sind."}
          </p>
          <div className="mt-4 rounded-md border border-line bg-canvas p-4">
            <QuestionForm
              key={q.fact_id as string}
              question={q}
              busy={busy}
              disabled={closed}
              onAnswer={(t) => onAnswer(q.fact_id as string, t)}
              onUnknown={() => onUnknown(q.fact_id as string)}
              onDefer={() => onDefer(q.fact_id as string, q.question_de)}
            />
          </div>
        </>
      ) : (
        <p className="mt-1 text-[13.5px] text-ink-muted">
          Alle wichtigen Angaben sind erfasst
          {(decision.intake?.deferred ?? 0) + (decision.intake?.unknown ?? 0) > 0
            ? "; zurückgestellte oder unbekannte Angaben bleiben im Fallbericht sichtbar."
            : "."}
        </p>
      )}
    </Section>
  );
}

/* ----------------------------------------------------------------------------------- B2 */
function Supplement({ decision, detail, busy, onAnswer, onUnknown, onSkip, onOpenMore }: Props) {
  const [asking, setAsking] = useState(false);
  const closed = detail.status === "CLOSED";
  // questions the backend still offers (required ones left open + optional ones), minus those already skipped
  const available = (decision.optional_open_facts ?? []).filter((m) => !m.deferred);
  const firstOptional = available[0];
  const current = firstOptional ? asQuestion(firstOptional, true) : null;

  return (
    <Section title="Ergänzende Angaben (optional)">
      <h2 className={h2}>Möchten Sie den Fall noch ergänzen?</h2>
      <p className="mt-1 text-[13.5px] text-ink-muted">
        Einige zusätzliche Angaben können der Fachperson helfen. Sie können diese Fragen überspringen.
      </p>

      {asking && current ? (
        <div className="mt-4 rounded-md border border-line bg-canvas p-4">
          <QuestionForm
            key={current.fact_id as string}
            question={current}
            busy={busy}
            disabled={closed}
            optionalMode
            onAnswer={(t) => onAnswer(current.fact_id as string, t)}
            onUnknown={() => onUnknown(current.fact_id as string)}
            onDefer={() => onSkip(current.fact_id as string)}
          />
          <Button variant="ghost" size="sm" className="mt-3" onClick={() => setAsking(false)}>
            Ergänzung beenden
          </Button>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
          {available.length > 0 && current ? (
            <>
              <span className="text-[13px] text-ink-muted">
                {available.length === 1 ? "1 ergänzende Frage verfügbar" : `${available.length} ergänzende Fragen verfügbar`}
              </span>
              <Button variant="secondary" size="sm" disabled={closed} onClick={() => setAsking(true)}>
                Ergänzende Fragen beantworten
              </Button>
            </>
          ) : (
            <span className="text-[13px] text-ink-muted">Es sind keine ergänzenden Fragen offen.</span>
          )}
          {!closed && (
            <button type="button" onClick={onOpenMore} className="text-[13px] font-medium text-brand-700 hover:underline">
              Andere Informationen ergänzen
            </button>
          )}
        </div>
      )}
    </Section>
  );
}

/* ----------------------------------------------------------------------------------- C */
function Report({ detail, decision, hasBriefing, briefingStale, briefingBusy, briefingError, onCreateBriefing, onRequestHandover, onCompleteHandover }: Props) {
  const urgent = decision.max_urgency === "HIGH";
  const closed = detail.status === "CLOSED";
  const h = detail.handover;

  return (
    <Section title="Fallbericht" accent="border-l-brand-500">
      <h2 className={h2}>Fallbericht</h2>
      <p className="mt-1 text-[13.5px] text-ink-muted">
        Die bisher erfassten Angaben werden für die zuständige Fachperson zusammengefasst. Offene Fragen und Unsicherheiten
        bleiben sichtbar. {urgent ? "Der Fallbericht ersetzt die dringende Kontaktaufnahme nicht." : "Der Fallbericht ist keine Kontaktaufnahme mit einer Fachperson."}
      </p>
      {hasBriefing && briefingStale && (
        <p role="status" className="mt-2 text-[13px] text-ask-fg">
          Seit dem letzten Fallbericht wurden neue Angaben erfasst.
        </p>
      )}
      {briefingError && (
        <p role="alert" className="mt-2 text-[13px] text-error-fg">
          Der Fallbericht konnte nicht erstellt werden: {briefingError} Ihre Angaben sind gespeichert. Bitte erneut versuchen.
        </p>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {hasBriefing && !briefingStale ? (
          <Button asChild variant="primary" size="lg">
            <Link to={`/cases/${detail.id}/briefing`}>
              <FileText /> Fallbericht ansehen
            </Link>
          </Button>
        ) : (
          <Button variant="primary" size="lg" loading={briefingBusy} onClick={onCreateBriefing}>
            <FileText /> {hasBriefing ? "Fallbericht aktualisieren" : "Fallbericht erstellen"}
          </Button>
        )}
        {hasBriefing && briefingStale && (
          <Link to={`/cases/${detail.id}/briefing`} className="text-[13px] font-medium text-brand-700 hover:underline">
            Letzten Fallbericht ansehen
          </Link>
        )}
        {hasBriefing && detail.latest_briefing_id && (
          <a
            href={`/api/cases/${detail.id}/briefings/${detail.latest_briefing_id}/pdf`}
            download
            className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline"
          >
            <Download className="size-3.5" aria-hidden /> PDF herunterladen
          </a>
        )}
      </div>

      <details className="group mt-5 border-t border-line pt-3">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[12.5px] font-medium text-brand-700 hover:underline">
          <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
          Übergabestatus verwalten
        </summary>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-[13px] text-ink-muted">
          <p className="max-w-lg">
            {!h || h.status === "RECOMMENDED"
              ? "Übergabe empfohlen. Es wurde noch niemand kontaktiert; das System verschickt nichts selbst."
              : h.status === "HANDOFF_REQUESTED"
                ? "Übergabe angefragt. Bestätigen Sie sie, sobald sie tatsächlich erfolgt ist."
                : `Übergabe bestätigt${h.completion_note ? `: ${h.completion_note}` : "."}`}
          </p>
          {(!h || h.status === "RECOMMENDED") && (
            <Button variant="secondary" size="sm" disabled={closed || !h} onClick={onRequestHandover}>
              Als angefragt markieren
            </Button>
          )}
          {h?.status === "HANDOFF_REQUESTED" && (
            <Button variant="secondary" size="sm" disabled={closed} onClick={onCompleteHandover}>
              Übergabe bestätigen
            </Button>
          )}
        </div>
      </details>
    </Section>
  );
}
