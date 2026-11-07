import { ArrowLeft, FileText } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { ACTION_META, ActionBadge, Badge, UrgencyBadge } from "@/components/shared/badges";
import { ErrorState, PageHeader, SectionLabel } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCase, useDecisions, useProfessionals } from "@/lib/queries";
import { cn, formatDateTime } from "@/lib/utils";

const OUTCOME = {
  FIRED: { label: "Ausgelöst", tone: "escalate" as const },
  NOT_FIRED: { label: "Nicht ausgelöst", tone: "neutral" as const },
  UNKNOWN: { label: "Unbekannt – Angabe fehlt", tone: "incomplete" as const },
};
const KIND = {
  GLOBAL_ESCALATION: "Globale Eskalationsregel",
  ISSUE_ESCALATION: "Eskalationsregel Rechtsgebiet",
  LEGAL_RULE: "Rechtliche Prüfregel",
  SYSTEM: "Systemregel",
};

export function DecisionPage() {
  const { caseId = "" } = useParams();
  const caseQ = useCase(caseId);
  const histQ = useDecisions(caseId);
  const { label: proLabel } = useProfessionals();

  if (caseQ.isError) return <ErrorState error={caseQ.error} onRetry={() => void caseQ.refetch()} />;
  if (!caseQ.data) return <Skeleton className="h-72" />;

  const detail = caseQ.data;
  const d = detail.current_decision;
  const meta = d ? ACTION_META[d.action] : null;
  const issueTitle = (id: string | null | undefined) =>
    id ? (detail.issues.find((i) => i.issue_definition_id === id)?.title_de ?? id) : null;

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to={`/cases/${caseId}`} className="inline-flex items-center gap-1 hover:text-ink">
            <ArrowLeft className="size-3.5" aria-hidden /> {detail.display_id} · {detail.title}
          </Link>
        }
        title="Entscheidungsbegründung"
        description="Warum das System aktuell diese Empfehlung gibt. Die Entscheidung folgt ausschliesslich expliziten Regeln der Wissensbasis, nicht dem Sprachmodell."
        actions={
          <Button asChild variant="secondary" size="sm">
            <Link to={`/cases/${caseId}/briefing`}>
              <FileText /> Expert Briefing
            </Link>
          </Button>
        }
      />

      {!d && (
        <Card>
          <CardContent className="py-8 text-center text-[13px] text-ink-muted">
            Noch keine Einschätzung vorhanden. {detail.analysis.status !== "OK" && "Die Analyse ist ausstehend oder fehlgeschlagen."}
          </CardContent>
        </Card>
      )}

      {d && meta && (
        <div className="space-y-4">
          <Card className={cn("border-l-4", d.action === "ASK" && "border-l-ask-solid", d.action === "PROCEED" && "border-l-proceed-solid", d.action === "ESCALATE" && "border-l-escalate-solid")}>
            <CardContent className="pt-5">
              <div className="flex flex-wrap items-center gap-3">
                <ActionBadge action={d.action} withCode />
                <UrgencyBadge urgency={d.max_urgency} />
                <span className="text-[12px] text-ink-subtle">
                  Stand {formatDateTime(d.evaluated_at)} · Knowledge Base <span className="font-mono">{d.knowledge_base_version}</span>
                </span>
              </div>
              <p className="mt-3 max-w-3xl text-[15px] leading-relaxed">{d.explanation_de}</p>
              <div className="mt-4 flex flex-wrap items-center gap-1.5">
                <span className="mr-1 text-[12px] text-ink-subtle">Reason Codes:</span>
                {d.reason_codes.map((c, i) => (
                  <Badge key={c} tone={i === 0 ? "brand" : "neutral"}>
                    <span className="font-mono">{c}</span>
                    {i === 0 && " · Hauptgrund"}
                  </Badge>
                ))}
              </div>
              {d.recommended_professionals.length > 0 && (
                <p className="mt-3 text-[13px] text-ink-muted">
                  Empfohlene Fachpersonen: {d.recommended_professionals.map(proLabel).join(", ")}
                </p>
              )}
            </CardContent>
          </Card>

          {Object.keys(d.derived_values ?? {}).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Interne Dringlichkeitswerte</CardTitle>
                <CardDescription>
                  Systemseitig aus den Angaben abgeleitet. Das sind Produktschwellen (z. B. 20 und 60 Tage), keine
                  gesetzlichen Fristen. Das System nennt kein Fristende.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-2 sm:grid-cols-2">
                  {Object.entries(d.derived_values ?? {}).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between rounded-md bg-sunken px-3 py-2 text-[13px]">
                      <dt className="text-ink-muted">
                        {k === "days_since_earliest_receipt"
                          ? "Tage seit frühestem Empfangshinweis"
                          : k === "days_until_termination_date"
                            ? "Tage bis zum Kündigungstermin"
                            : k}
                      </dt>
                      <dd className="font-medium tabular-nums">{v ?? "unbekannt"}</dd>
                    </div>
                  ))}
                </dl>
              </CardContent>
            </Card>
          )}

          {(d.related_routes ?? []).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Verweis auf andere Issues</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-[13px]">
                {(d.related_routes ?? []).map((r) => (
                  <div key={r.issue_id}>
                    <strong>{r.title_de}</strong>{" "}
                    <Badge tone={r.available ? "proceed" : "incomplete"}>{r.available ? "Dossierstand, nicht freigegeben" : "noch nicht verfügbar"}</Badge>
                    <p className="mt-0.5 text-ink-muted">
                      {r.note_de} <span className="font-mono text-[11.5px]">({r.from_rule_id})</span>
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Ausgelöste Regeln</CardTitle>
                <CardDescription>Eskalationsauslöser</CardDescription>
              </CardHeader>
              <CardContent>
                {d.triggered_rules.length === 0 ? (
                  <p className="text-[13px] text-ink-muted">Keine Eskalationsregel ausgelöst.</p>
                ) : (
                  <ul className="space-y-3">
                    {d.triggered_rules.map((r) => (
                      <li key={r.rule_id} className="rounded-md border border-escalate-line bg-escalate-bg/40 p-3">
                        <p className="text-[13.5px]">{r.reason_de}</p>
                        <div className="mt-2 flex flex-wrap gap-1.5 text-[11.5px]">
                          <Badge tone="neutral">
                            <span className="font-mono">{r.rule_id}</span>
                          </Badge>
                          <Badge tone="neutral">
                            <span className="font-mono">{r.reason_code}</span>
                          </Badge>
                          <Badge tone="neutral">{r.scope === "GLOBAL" ? "Global" : r.scope === "SYSTEM" ? "System" : (issueTitle(r.issue_id) ?? "Rechtsgebiet")}</Badge>
                          <Badge tone={r.urgency === "HIGH" ? "escalate" : "neutral"}>Dringlichkeit: {r.urgency_label_de}</Badge>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Fehlende Informationen</CardTitle>
                <CardDescription>Pflichtangaben, die noch nicht geklärt sind</CardDescription>
              </CardHeader>
              <CardContent>
                {d.missing_facts.length === 0 ? (
                  <p className="text-[13px] text-ink-muted">Alle erforderlichen Angaben liegen vor.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {d.missing_facts.map((m) => (
                      <li key={m.fact_id} className="flex items-start justify-between gap-3 py-2 text-[13px]">
                        <div>
                          <p className="font-medium">{m.label_de}</p>
                          <p className="text-[12px] text-ink-subtle">{m.why_needed_de}</p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1">
                          <Badge tone={m.status === "MISSING" ? "incomplete" : m.status === "AMBIGUOUS" ? "ask" : "escalate"}>
                            {m.status === "MISSING" ? "Fehlt" : m.status === "AMBIGUOUS" ? "Unklar" : "Widersprüchlich"}
                          </Badge>
                          {m.deferred && <Badge tone="neutral">Zurückgestellt</Badge>}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {d.legal_findings.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Rechtliche Hinweise aus der Wissensbasis</CardTitle>
                <CardDescription>
                  Prüfregeln, die zutreffen. Hinweise für die Fachperson, keine Rechtsauskunft.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {d.legal_findings.map((f) => (
                    <li key={f.rule_id} className="rounded-md border border-line bg-sunken p-3 text-[13px]">
                      {f.result_de}
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        <Badge tone="neutral">
                          <span className="font-mono">{f.rule_id}</span>
                        </Badge>
                        {f.legal_source_ids.map((s) => (
                          <Badge key={s} tone="unverified">
                            Quelle <span className="font-mono">{s}</span> · nicht verifiziert
                          </Badge>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Geprüfte Regeln ({d.evaluated_rules.length})</CardTitle>
              <CardDescription>Vollständige Liste – nachvollziehbar, welche Regel wie ausgewertet wurde.</CardDescription>
            </CardHeader>
            <CardContent>
              <details>
                <summary className="cursor-pointer text-[13px] font-medium text-brand-600 hover:underline">
                  Technische Details anzeigen
                </summary>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-[12.5px]">
                    <thead>
                      <tr className="border-b border-line text-ink-subtle">
                        <th className="py-1.5 pr-3 font-medium">Regel</th>
                        <th className="py-1.5 pr-3 font-medium">Art</th>
                        <th className="py-1.5 pr-3 font-medium">Rechtsgebiet</th>
                        <th className="py-1.5 font-medium">Ergebnis</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.evaluated_rules.map((r) => (
                        <tr key={r.rule_id} className="border-b border-line last:border-0">
                          <td className="py-1.5 pr-3 font-mono">{r.rule_id}</td>
                          <td className="py-1.5 pr-3">{KIND[r.kind]}</td>
                          <td className="py-1.5 pr-3">{issueTitle(r.issue_id) ?? "–"}</td>
                          <td className="py-1.5">
                            <Badge tone={OUTCOME[r.outcome].tone}>{OUTCOME[r.outcome].label}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Verlauf der Einschätzungen</CardTitle>
              <CardDescription>Jede Änderung der Empfehlung wird gespeichert.</CardDescription>
            </CardHeader>
            <CardContent>
              <SectionLabel>Neueste zuerst</SectionLabel>
              <ol className="mt-2 divide-y divide-line">
                {(histQ.data ?? []).map((h) => (
                  <li key={h.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-[12.5px]">
                    <span className="w-36 text-ink-subtle">{formatDateTime(h.created_at)}</span>
                    <ActionBadge action={h.decision.action} />
                    <span className="font-mono text-ink-muted">{h.decision.main_reason_code}</span>
                    <span className="ml-auto text-ink-subtle">Fallstand v{h.case_version}</span>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
