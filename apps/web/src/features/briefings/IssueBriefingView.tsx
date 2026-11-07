import { SourceChip } from "@/components/shared/SourceInfo";
import { ArrowRight, FileStack, Landmark } from "lucide-react";
import { Badge, EvidenceBadge, FactStatusBadge, UrgencyBadge } from "@/components/shared/badges";
import type { IssueBriefing } from "@/types";

/** Issue-specific briefing (layout defined by the law team in the knowledge base). */
export function IssueBriefingView({ ib }: { ib: IssueBriefing }) {
  const urgency = ib.max_urgency as "HIGH" | "MEDIUM" | "LOW" | null;
  const open = ib.open_questions.length;

  return (
    <section aria-labelledby="issue-briefing" className="border-b border-line-strong pb-6" data-testid="issue-briefing">
      <h2 id="issue-briefing" className="flex flex-wrap items-center gap-2 text-[17px] font-semibold">
        Fachliche Übersicht: {ib.title_de}
        {ib.canton && <Badge tone="brand">Kanton {ib.canton}</Badge>}
      </h2>
      <p className="mt-2 text-[13.5px] leading-relaxed">
        <span className="mr-1.5 text-[11.5px] font-medium uppercase tracking-wide text-ink-subtle">Anliegen</span>
        <br />
        {ib.concern_de}
      </p>

      <div className="mt-4 rounded-md border border-line bg-sunken px-3.5 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <UrgencyBadge urgency={urgency} />
          {!urgency && <Badge tone="neutral">Keine Eskalationsregel ausgelöst</Badge>}
          {ib.derived.map((d) => (
            <span key={d.id} className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-muted">
              {d.label_de}: <strong className="tabular-nums text-ink">{d.value ?? "unbekannt"}</strong>
              <EvidenceBadge level="SYSTEM_DERIVED" />
            </span>
          ))}
        </div>
        <p className="mt-2 text-[12px] text-ink-subtle">{ib.urgency_note_de}</p>
      </div>

      <h3 className="mt-6 text-[13px] font-semibold">Ausgelöste Regeln</h3>
      {ib.triggered_rules.length === 0 ? (
        <p className="mt-1 text-[13px] text-ink-subtle">Keine Regel ausgelöst.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {ib.triggered_rules.map((r) => (
            <li key={r.rule_id} className="print-break-avoid rounded-md border border-line p-3 text-[13px]">
              <p>{r.reason_de}</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5 text-[11.5px]">
                <Badge tone="neutral">
                  Regel <span className="font-mono">{r.rule_id}</span>
                </Badge>
                <Badge tone="neutral">
                  Code <span className="font-mono">{r.reason_code}</span>
                </Badge>
                <Badge tone={r.urgency === "HIGH" ? "escalate" : "neutral"}>Dringlichkeit: {r.urgency_label_de}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}

      {ib.groups.map((g) => (
        <div key={g.id} className="print-break-avoid mt-6">
          <h3 className="text-[13px] font-semibold">{g.title_de}</h3>
          <div className="mt-1.5 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[12.5px]">
              <tbody>
                {g.rows.map((r) => (
                  <tr key={r.fact_id} className="border-b border-line align-top last:border-0">
                    <td className="w-[34%] py-1.5 pr-3 text-ink-muted">{r.label_de}</td>
                    <td className="w-[22%] py-1.5 pr-3 font-medium">
                      {r.status === "KNOWN" ? r.value_display : <FactStatusBadge status={r.status} />}
                    </td>
                    <td className="py-1.5">
                      <EvidenceBadge level={r.evidence_level} />
                      {r.evidence_quote && (
                        <span className="ml-2 text-ink-subtle">
                          <q className="not-italic">{r.evidence_quote}</q>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      <div className="print-break-avoid mt-6 grid gap-5 sm:grid-cols-2">
        <div>
          <h3 className="text-[13px] font-semibold">Offene Fragen ({open})</h3>
          {open === 0 ? (
            <p className="mt-1 text-[13px] text-ink-subtle">Keine offenen Pflichtfragen.</p>
          ) : (
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[12.5px] text-ink-muted">
              {ib.open_questions.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          )}
          {ib.unknown_facts.length > 0 && (
            <p className="mt-2 text-[12.5px] text-ink-muted">
              Gefragt, aber unbekannt: <strong>{ib.unknown_facts.join(", ")}</strong>
            </p>
          )}
        </div>
        <div>
          <h3 className="flex items-center gap-1.5 text-[13px] font-semibold">
            <FileStack className="size-3.5" aria-hidden /> Anzufordernde Dokumente
          </h3>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[12.5px] text-ink-muted">
            {ib.documents_to_request.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-6">
        <h3 className="text-[13px] font-semibold">Juristische Prüfpunkte mit Quellen</h3>
        {ib.statements_suppressed ? (
          <p className="mt-1 text-[13px] text-ink-subtle">
            Fall ausserhalb des Moduls: Standard-Prüfpunkte werden bewusst nicht ausgegeben.
          </p>
        ) : (
          <ul className="mt-2 space-y-2.5">
            {ib.review_points.map((p) => (
              <li key={p.text_de} className="print-break-avoid text-[13px]">
                <span className="mr-1.5 inline-flex items-center text-brand-600">
                  <ArrowRight className="size-3.5" aria-hidden />
                </span>
                {p.text_de}
                {p.triggered && <Badge tone="brand" className="ml-1.5">durch Regel ausgelöst</Badge>}
                <div className="mt-1 flex flex-wrap gap-1.5 pl-5">
                  {p.source_ids.map((id) => (
                    <SourceChip key={id} id={id} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="print-break-avoid mt-6">
        <h3 className="flex items-center gap-1.5 text-[13px] font-semibold">
          <Landmark className="size-3.5" aria-hidden /> Zuständige Stellen (Kanton Zürich)
        </h3>
        <ul className="mt-2 space-y-2">
          {ib.authorities.map((a) => (
            <li key={a.id} className="rounded-md border border-line p-2.5 text-[12.5px]">
              <p className="font-medium">{a.name_de}</p>
              <p className="text-ink-muted">{a.purpose_de}</p>
              {a.scope_de && <p className="text-ink-muted">{a.scope_de}</p>}
              {a.cost_de && <p className="text-ink-muted">Kosten (laut Dossier): {a.cost_de}</p>}
              <p className="mt-1">
                <Badge tone={a.contact_verified ? "proceed" : "incomplete"}>
                  {a.contact_verified ? `Kontakt geprüft am ${a.verified_at}` : "Kontaktdaten nicht verifiziert"}
                </Badge>
                {a.url_hint && <span className="ml-2 text-ink-subtle">{a.url_hint}</span>}
              </p>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11.5px] text-ink-subtle">
          Telefonnummern, Öffnungszeiten und Kosten wurden nicht auf den offiziellen Seiten geprüft; vor der Weitergabe
          bestätigen. Die zuständige Schlichtungsbehörde richtet sich nach dem Ort der Wohnung.
        </p>
      </div>
    </section>
  );
}
