import { FedlexBadges, FedlexDetails } from "@/components/shared/SourceInfo";
import type { ReactNode } from "react";
import { ActionBadge, Badge, DossierBadge, EvidenceBadge, VerificationBadge } from "@/components/shared/badges";
import { IssueBriefingView } from "./IssueBriefingView";
import { formatDateTime } from "@/lib/utils";
import type { BriefingView, CaseBriefing } from "@/types";

const TITLES: Record<string, string> = {
  overview: "Fallübersicht",
  legal_areas: "Erkannte Rechtsgebiete",
  known_facts: "Bekannte Fakten",
  missing_information: "Fehlende Informationen",
  uncertainties: "Widersprüche und Unklarheiten",
  legal_sources: "Relevante Rechtsquellen",
  legal_risks: "Erkannte rechtliche Risiken",
  decision_rationale: "Entscheidungsbegründung",
  escalation_reasons: "Eskalationsgründe",
  recommended_professionals: "Empfohlene Fachpersonen",
  next_steps: "Nächste Schritte",
};

function Section({ n, id, children }: { n: number; id: string; children: ReactNode }) {
  return (
    <section className="print-break-avoid border-t border-line py-5 first:border-t-0" aria-labelledby={`sec-${id}`}>
      <h2 id={`sec-${id}`} className="mb-3 flex items-baseline gap-2.5 text-[15px] font-semibold">
        <span className="font-mono text-[12px] text-ink-subtle">{String(n).padStart(2, "0")}</span>
        {TITLES[id] ?? id}
      </h2>
      {children}
    </section>
  );
}

const Empty = ({ children }: { children: ReactNode }) => <p className="text-[13px] text-ink-subtle">{children}</p>;

function renderSection(id: string, b: CaseBriefing): ReactNode {
  switch (id) {
    case "overview":
      return (
        <>
          <dl className="grid gap-x-8 gap-y-2 text-[13px] sm:grid-cols-2">
            <div className="flex justify-between gap-3 border-b border-line py-1.5">
              <dt className="text-ink-muted">Fallnummer</dt>
              <dd className="font-mono">{b.overview.case_display_id}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-line py-1.5">
              <dt className="text-ink-muted">Einschätzung</dt>
              <dd>
                <ActionBadge action={b.overview.action} />
              </dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-line py-1.5">
              <dt className="text-ink-muted">Erfasste Eingaben</dt>
              <dd>{b.overview.message_count}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-line py-1.5">
              <dt className="text-ink-muted">Fallstand</dt>
              <dd>v{b.case_version}</dd>
            </div>
          </dl>
          <p className="mt-3 text-[13.5px] leading-relaxed">
            {b.overview.summary ? (
              <>
                <span className="mr-1.5 text-[11.5px] font-medium uppercase tracking-wide text-ink-subtle">
                  Zusammenfassung (KI-erstellt, aus den Eingaben)
                </span>
                <br />
                {b.overview.summary}
              </>
            ) : (
              <span className="text-ink-subtle">Keine Zusammenfassung vorhanden.</span>
            )}
          </p>
        </>
      );
    case "legal_areas":
      return b.legal_areas.length + b.unsupported_issues.length === 0 ? (
        <Empty>Kein Rechtsgebiet erkannt.</Empty>
      ) : (
        <ul className="space-y-2 text-[13px]">
          {b.legal_areas.map((i) => (
            <li key={i.issue_id} className="flex flex-wrap items-baseline gap-2">
              <strong>{i.title_de}</strong>
              {i.confidence != null && <span className="text-ink-subtle">Sicherheit KI: {Math.round(i.confidence * 100)} %</span>}
              {i.evidence && (
                <span className="text-ink-muted">
                  Beleg: <q className="not-italic">{i.evidence}</q>
                </span>
              )}
            </li>
          ))}
          {b.unsupported_issues.map((u, k) => (
            <li key={k} className="flex flex-wrap items-baseline gap-2">
              <strong>{u.description}</strong>
              <Badge tone="escalate">Nicht von der Wissensbasis abgedeckt</Badge>
              {u.evidence && (
                <span className="text-ink-muted">
                  Beleg: <q className="not-italic">{u.evidence}</q>
                </span>
              )}
            </li>
          ))}
        </ul>
      );
    case "known_facts":
      return b.known_facts.length === 0 ? (
        <Empty>Noch keine Fakten erfasst.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-ink-subtle">
                <th className="py-1.5 pr-3 font-semibold">Angabe</th>
                <th className="py-1.5 pr-3 font-semibold">Wert</th>
                <th className="py-1.5 font-semibold">Herkunft / Beleg</th>
              </tr>
            </thead>
            <tbody>
              {b.known_facts.map((f) => (
                <tr key={f.fact_id} className="border-b border-line align-top last:border-0">
                  <td className="py-2 pr-3 text-ink-muted">{f.label_de}</td>
                  <td className="py-2 pr-3 font-medium">{f.value_display}</td>
                  <td className="py-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <EvidenceBadge level={f.evidence_level ?? "AI_EXTRACTED"} />
                    </div>
                    {f.evidence_quote && (
                      <p className="mt-1 text-[12px] text-ink-muted">
                        <q className="not-italic">{f.evidence_quote}</q>
                      </p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11.5px] text-ink-subtle">
            «Aus Schilderung extrahiert» bedeutet: von der KI aus dem Gesprächstext abgeleitet und noch nicht von der
            Fachperson bestätigt.
          </p>
        </div>
      );
    case "missing_information":
      return b.missing_information.length === 0 ? (
        <Empty>Keine offenen Pflichtangaben.</Empty>
      ) : (
        <ul className="space-y-1.5 text-[13px]">
          {b.missing_information.map((m) => (
            <li key={m.fact_id}>
              <strong>{m.label_de}</strong> <span className="text-ink-subtle">– {m.question_de}</span>
              {m.deferred && <Badge tone="neutral" className="ml-2">Zurückgestellt</Badge>}
            </li>
          ))}
        </ul>
      );
    case "uncertainties":
      return b.uncertainties.length === 0 ? (
        <Empty>Keine Widersprüche oder unklaren Angaben.</Empty>
      ) : (
        <ul className="space-y-1.5 text-[13px]">
          {b.uncertainties.map((u) => (
            <li key={u.fact_id}>
              <strong>{u.label_de}</strong>{" "}
              <Badge tone={u.status === "CONTRADICTORY" ? "escalate" : "ask"}>
                {u.status === "CONTRADICTORY" ? "Widersprüchlich" : "Unklar"}
              </Badge>
              {u.values.length > 0 && <span className="ml-2 text-ink-muted">Angaben: {u.values.join(" / ")}</span>}
            </li>
          ))}
        </ul>
      );
    case "legal_sources":
      return b.legal_sources.length === 0 ? (
        <Empty>Keine Rechtsquellen referenziert.</Empty>
      ) : (
        <>
          <ul className="space-y-3">
            {b.legal_sources.map((s) => (
              <li key={s.source.id} className="print-break-avoid rounded-md border border-line p-3 text-[13px]">
                <div className="flex flex-wrap items-center gap-2">
                  <strong>{s.source.citation ?? s.source.title_de}</strong>
                  <DossierBadge status={s.source.dossier_status} />
                  {s.source.fedlex && s.source.fedlex.retrieval_status !== "NOT_APPLICABLE" ? (
                    <FedlexBadges info={s.source.fedlex} />
                  ) : (
                    <VerificationBadge status={s.source.verification_status} />
                  )}
                </div>
                <p className="mt-0.5 font-mono text-[11.5px] text-ink-subtle">
                  {s.source.id}
                  {s.source.case_number && ` · ${s.source.case_number}`}
                  {s.source.decision_date && ` · ${s.source.decision_date}`}
                  {s.source.sr_number && ` · SR ${s.source.sr_number}`}
                  {s.source.valid_as_of && ` · Stand ${s.source.valid_as_of}`}
                  {s.source.origin_ref && ` · ${s.source.origin_ref}`}
                </p>
                {s.source.fedlex && <FedlexDetails info={s.source.fedlex} />}
                {s.source.text_de && (
                  <p className="mt-1.5 text-ink-muted">
                    {s.source.fedlex?.origin !== "NONE" && s.source.fedlex?.retrieval_status.startsWith("RETRIEVED") && (
                      <span className="mr-1 text-[11px] font-medium text-ink-subtle">Zitat im Law-Dossier:</span>
                    )}
                    {s.source.text_de}
                  </p>
                )}
                {s.source.core_statement_de && <p className="mt-1.5 text-ink-muted">{s.source.core_statement_de}</p>}
                {s.source.considerations && s.source.considerations.length > 0 && (
                  <p className="mt-1 text-[11.5px] text-ink-subtle">Fundstellen: {s.source.considerations.join("; ")}</p>
                )}
                <p className="mt-1 font-mono text-[11px] text-ink-subtle">Referenziert von: {s.referenced_by.join(", ")}</p>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11.5px] text-ink-subtle">
            «Im Law-Dossier geprüft» ist der Prüfstand laut Law-Team. «Amtlicher Text abgerufen» bedeutet nur, dass der
            Gesetzestext bei Fedlex gefunden und gespeichert wurde. Ob eine Rechtsfolge im konkreten Fall eintritt,
            sagt ein Abruf nicht aus; die Auslegung prüft die Fachperson. Bundesgerichtsentscheide sind nicht an Fedlex
            angebunden und stammen aus dem Dossier.
          </p>
        </>
      );
    case "legal_risks":
      return (
        <>
          {b.legal_risks.length === 0 ? (
            <Empty>Keine Hinweise aus den Prüfregeln.</Empty>
          ) : (
            <ul className="space-y-2 text-[13px]">
              {b.legal_risks.map((r) => (
                <li key={r.rule_id}>
                  {r.result_de} <span className="font-mono text-[11.5px] text-ink-subtle">({r.rule_id})</span>
                </li>
              ))}
            </ul>
          )}
          {(b.approved_statements ?? []).length > 0 && (
            <div className="mt-4">
              <p className="mb-1.5 text-[12px] font-semibold text-ink-muted">Freigegebene allgemeine Hinweise (mit Quelle)</p>
              <ul className="space-y-1.5 text-[13px]">
                {(b.approved_statements ?? []).map((a) => (
                  <li key={a.rule_id}>
                    {a.text_de} <span className="font-mono text-[11px] text-ink-subtle">({a.source_ids.join(", ")})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(b.related_routes ?? []).length > 0 && (
            <div className="mt-4 text-[13px]">
              <p className="mb-1.5 text-[12px] font-semibold text-ink-muted">Verweise auf andere Issues</p>
              <ul className="space-y-1">
                {(b.related_routes ?? []).map((r) => (
                  <li key={r.issue_id}>
                    {r.title_de}: {r.note_de}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      );
    case "decision_rationale":
      return (
        <div className="text-[13.5px]">
          <div className="flex flex-wrap items-center gap-2">
            <ActionBadge action={b.decision.action} withCode />
            {b.decision.reason_codes.map((c) => (
              <Badge key={c} tone="neutral">
                <span className="font-mono">{c}</span>
              </Badge>
            ))}
          </div>
          <p className="mt-2 leading-relaxed">{b.decision.explanation_de}</p>
          <p className="mt-2 text-[12px] text-ink-subtle">
            {b.decision.rules_evaluated} Regeln geprüft, {b.decision.rules_triggered.length} ausgelöst
            {b.decision.rules_triggered.length > 0 && `: ${b.decision.rules_triggered.join(", ")}`}. Wissensbasis{" "}
            {b.knowledge_base_version}.
          </p>
        </div>
      );
    case "escalation_reasons":
      return b.escalation_reasons.length === 0 ? (
        <Empty>Keine Eskalationsgründe.</Empty>
      ) : (
        <ul className="space-y-2 text-[13px]">
          {b.escalation_reasons.map((r) => (
            <li key={r.rule_id}>
              {r.reason_de}{" "}
              <span className="font-mono text-[11.5px] text-ink-subtle">
                ({r.rule_id} · {r.reason_code})
              </span>
            </li>
          ))}
        </ul>
      );
    case "recommended_professionals":
      return (
        <div className="text-[13px]">
          {b.recommended_professionals.length === 0 ? (
            <Empty>Keine Empfehlung.</Empty>
          ) : (
            <ul className="space-y-1">
              {b.recommended_professionals.map((p) => (
                <li key={p.id}>
                  <strong>{p.label_de}</strong> <span className="text-ink-subtle">– {p.description_de}</span>
                </li>
              ))}
            </ul>
          )}
          {b.handover && <p className="mt-2 text-ink-muted">Übergabestatus: {b.handover.note}</p>}
        </div>
      );
    case "next_steps":
      return (
        <ol className="list-decimal space-y-1 pl-5 text-[13px]">
          {b.next_steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      );
    default:
      return null;
  }
}

export function BriefingDocument({ view }: { view: BriefingView }) {
  const b = view.briefing;
  return (
    <article className="print-shell rounded-lg border border-line bg-surface p-6 shadow-card sm:p-9" aria-label="Expert Briefing">
      <header className="mb-2 border-b border-line-strong pb-5">
        <p className="text-[11.5px] font-semibold uppercase tracking-[0.08em] text-brand-600">Expert Briefing</p>
        <h1 className="mt-1 text-[24px] font-semibold leading-tight">{b.overview.title}</h1>
        <p className="mt-1.5 text-[12.5px] text-ink-muted">
          <span className="font-mono">{b.overview.case_display_id}</span> · Version {view.version} · erstellt{" "}
          {formatDateTime(view.created_at)} · Fallstand v{view.case_version} · Wissensbasis{" "}
          <span className="font-mono">{b.knowledge_base_version}</span>
        </p>
        <div className="mt-4 space-y-2">
          {b.knowledge_base_notice && (
            <p className="rounded-md bg-warning-bg px-3 py-2 text-[12.5px] text-warning-fg">{b.knowledge_base_notice}</p>
          )}
          <p className="rounded-md bg-sunken px-3 py-2 text-[12.5px] text-ink-muted">
            {b.ai_mode_notice} Dieses Briefing ist eine strukturierte Fallübersicht und keine Rechtsauskunft. Die
            Verantwortung liegt bei der zuständigen Fachperson.
          </p>
        </div>
      </header>
      {(b.issue_briefings ?? []).map((ib) => (
        <IssueBriefingView key={ib.issue_id} ib={ib} />
      ))}
      {b.section_order.map((id, i) => (
        <Section key={id} n={i + 1} id={id}>
          {renderSection(id, b)}
        </Section>
      ))}
    </article>
  );
}
