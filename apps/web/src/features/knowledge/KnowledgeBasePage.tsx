import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, CircleX, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Badge, VerificationBadge } from "@/components/shared/badges";
import { ErrorState, PageHeader } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { errorMessage, keys } from "@/lib/queries";

const CONTENT_STATUS: Record<string, { label: string; tone: "ask" | "neutral" | "proceed" }> = {
  DEMO_SYNTHETIC: { label: "Demo / synthetisch – nicht juristisch geprüft", tone: "ask" },
  DRAFT: { label: "Entwurf", tone: "neutral" },
  LEGALLY_REVIEWED: { label: "Juristisch geprüft", tone: "proceed" },
};

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3.5 shadow-xs">
      <div className="text-[12px] text-ink-muted">{label}</div>
      <div className="mt-1 text-[22px] font-semibold tabular-nums leading-none">{value}</div>
    </div>
  );
}

export function KnowledgeBasePage() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: keys.kbStatus, queryFn: api.kbStatus });
  const issues = useQuery({ queryKey: keys.kbIssues, queryFn: api.kbIssues });
  const reload = useMutation({
    mutationFn: api.kbReload,
    onSuccess: (s) => {
      qc.setQueryData(keys.kbStatus, s);
      void qc.invalidateQueries({ queryKey: keys.kbIssues });
      void qc.invalidateQueries({ queryKey: keys.status });
      s.valid ? toast.success("Knowledge Base neu geladen – gültig") : toast.error(`Neu geladen: ${s.errors.length} Fehler`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const s = status.data;
  return (
    <>
      <PageHeader
        title="Knowledge Base"
        description="Schreibgeschützte Übersicht der geladenen YAML-Dateien. Inhalte pflegt das Law-Team in knowledge_base/."
        actions={
          <Button variant="secondary" loading={reload.isPending} onClick={() => reload.mutate()}>
            <RefreshCw /> YAML neu laden
          </Button>
        }
      />
      {status.isError && <ErrorState error={status.error} onRetry={() => void status.refetch()} />}
      {status.isLoading && <Skeleton className="h-64" />}
      {s && (
        <div className="space-y-5">
          <div
            role="status"
            className={`flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3 text-[13px] ${
              s.valid ? "border-proceed-line bg-proceed-bg text-proceed-fg" : "border-error-line bg-error-bg text-error-fg"
            }`}
          >
            {s.valid ? <CircleCheck className="size-4" aria-hidden /> : <CircleX className="size-4" aria-hidden />}
            <strong>{s.valid ? "Schema-Validierung bestanden" : `${s.errors.length} Validierungsfehler`}</strong>
            <span className="font-mono text-[12px]">{s.version}</span>
          </div>

          {!s.valid && (
            <Card>
              <CardHeader>
                <CardTitle>Fehler</CardTitle>
                <CardDescription>
                  Fehlerhafte Dateien werden nicht geladen. Betroffene Rechtsgebiete werden dann als «nicht abgedeckt» behandelt
                  und eskaliert, niemals als sicher.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1 font-mono text-[12px] text-error-fg">
                  {s.errors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="Rechtsgebiete" value={s.issue_count} />
            <Stat label="Eskalationsregeln" value={s.escalation_rule_count} />
            <Stat label="Prüfregeln" value={s.legal_rule_count} />
            <Stat label="Globale Regeln" value={s.global_rule_count} />
            <Stat label="Quellen" value={`${s.source_count - s.unverified_source_count} / ${s.source_count} verifiziert`} />
            <Stat label="Testszenarien" value={s.scenario_count} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Rechtsgebiete</CardTitle>
            </CardHeader>
            <CardContent>
              {issues.isLoading && <Skeleton className="h-24" />}
              <div className="grid gap-3 lg:grid-cols-2">
                {(issues.data ?? []).map((i) => {
                  const cs = CONTENT_STATUS[i.content_status] ?? { label: i.content_status, tone: "neutral" as const };
                  return (
                    <div key={i.id} className="rounded-lg border border-line p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <strong className="text-[14px]">{i.title_de}</strong>
                        <span className="font-mono text-[11.5px] text-ink-subtle">
                          {i.id} · v{i.version}
                        </span>
                      </div>
                      <div className="mt-1.5">
                        <Badge tone={cs.tone}>{cs.label}</Badge>
                      </div>
                      <p className="mt-2 text-[12.5px] text-ink-muted">{i.description}</p>
                      <p className="mt-2 text-[12px] text-ink-subtle">
                        {i.fact_count} Fakten ({i.required_fact_count} erforderlich) · {i.legal_rule_count} Prüfregeln ·{" "}
                        {i.escalation_rule_count} Eskalationsregeln
                      </p>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Geladene Dateien</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[12.5px]">
                <thead>
                  <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-ink-subtle">
                    <th className="py-2 pr-3 font-semibold">Datei</th>
                    <th className="py-2 pr-3 font-semibold">Art</th>
                    <th className="py-2 pr-3 font-semibold">Version</th>
                    <th className="py-2 pr-3 font-semibold">Regeln/Einträge</th>
                    <th className="py-2 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {s.files.map((f) => (
                    <tr key={f.path} className="border-b border-line align-top last:border-0">
                      <td className="py-2 pr-3 font-mono">{f.path}</td>
                      <td className="py-2 pr-3">{f.kind}</td>
                      <td className="py-2 pr-3 font-mono">{f.version ?? "–"}</td>
                      <td className="py-2 pr-3">{f.rule_count || "–"}</td>
                      <td className="py-2">
                        {f.ok ? <Badge tone="proceed">OK</Badge> : <Badge tone="error">Fehler</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Rechtsquellen</CardTitle>
              <CardDescription>
                Nur Metadaten aus der Wissensbasis. Ein Live-Abruf bei Fedlex ist noch nicht implementiert, daher gilt keine
                Quelle als verifiziert.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-[12.5px]">
                <tbody>
                  {s.sources.map((src) => (
                    <tr key={src.id} className="border-b border-line last:border-0">
                      <td className="py-2 pr-3 font-mono">{src.id}</td>
                      <td className="py-2 pr-3">{src.title_de}</td>
                      <td className="py-2 pr-3 text-ink-subtle">
                        {src.provider} · SR {src.sr_number ?? "–"} · Art. {src.article ?? "–"}
                      </td>
                      <td className="py-2">
                        <VerificationBadge status={src.verification_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
