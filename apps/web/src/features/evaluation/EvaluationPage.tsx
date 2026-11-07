import { useMutation, useQuery } from "@tanstack/react-query";
import { CircleCheck, CircleX, Play } from "lucide-react";
import { toast } from "sonner";
import { ActionBadge, Badge } from "@/components/shared/badges";
import { ErrorState, PageHeader } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/queries";
import type { Action, EvaluationSummary } from "@/types";

function Tile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-xs">
      <div className="text-[12px] font-medium text-ink-muted">{label}</div>
      <div className="mt-1.5 text-[26px] font-semibold leading-none tabular-nums">{value}</div>
      {hint && <div className="mt-2 text-[12px] text-ink-subtle">{hint}</div>}
    </div>
  );
}

const VALIDATION = {
  SYNTHETIC_TECHNICAL: { label: "Synthetisch-technisch", tone: "unverified" as const },
  LEGALLY_VALIDATED: { label: "Juristisch validiert", tone: "proceed" as const },
};

export function EvaluationPage() {
  const scenarios = useQuery({ queryKey: ["eval-scenarios"], queryFn: api.evaluationScenarios });
  const run = useMutation({
    mutationFn: api.runEvaluation,
    onSuccess: (r: EvaluationSummary) =>
      r.failed === 0 ? toast.success(`${r.passed} von ${r.total} Szenarien bestanden`) : toast.error(`${r.failed} Szenario(en) fehlgeschlagen`),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const r = run.data;

  return (
    <>
      <PageHeader
        title="Evaluation"
        description="Prüft die deterministische Entscheidungslogik gegen definierte Testszenarien. Es werden keine KI-Aufrufe gemacht."
        actions={
          <Button variant="primary" loading={run.isPending} onClick={() => run.mutate()}>
            <Play /> Evaluation ausführen
          </Button>
        }
      />

      <div className="mb-5 rounded-lg border border-unverified-line bg-unverified-bg px-4 py-3 text-[13px] text-unverified-fg">
        {r ? (
          <>
            <strong>{r.synthetic_total}</strong> synthetisch-technische und <strong>{r.legally_validated_total}</strong>{" "}
            juristisch validierte Szenarien. Das Ergebnis zeigt nur, ob die Engine die hinterlegten Regeln wie spezifiziert
            ausführt, nicht, ob die Regeln juristisch korrekt sind.
          </>
        ) : (
          <>
            Alle Szenarien sind derzeit <strong>synthetisch-technisch</strong>. Juristisch validierte Szenarien liefert
            das Law-Team. Es wird bewusst keine Genauigkeitsquote berechnet.
          </>
        )}
      </div>

      {run.isError && <ErrorState error={run.error} onRetry={() => run.mutate()} />}

      {r && (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Tile label="Szenarien" value={r.total} />
          <Tile label="Bestanden" value={`${r.passed} / ${r.total}`} hint="erwartete Entscheidung erreicht" />
          <Tile label="Fehlgeschlagen" value={r.failed} />
          <Tile label="Fehlende Eskalationen" value={r.missed_escalations} hint="Eskalation erwartet, nicht erfolgt" />
          <Tile label="Unnötige Eskalationen" value={r.unnecessary_escalations} hint="Eskalation erfolgt, nicht erwartet" />
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{r ? "Ergebnisse" : "Verfügbare Szenarien"}</CardTitle>
          <CardDescription>
            {r ? `Knowledge Base ${r.knowledge_base_version}` : "Noch nicht ausgeführt – starten Sie die Evaluation oben rechts."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {scenarios.isLoading && <Skeleton className="h-40" />}
          {scenarios.isError && <ErrorState error={scenarios.error} onRetry={() => void scenarios.refetch()} />}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-[13px]">
              <thead>
                <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-ink-subtle">
                  <th className="py-2 pr-3 font-semibold">Szenario</th>
                  <th className="py-2 pr-3 font-semibold">Art</th>
                  <th className="py-2 pr-3 font-semibold">Erwartet</th>
                  {r && <th className="py-2 pr-3 font-semibold">Tatsächlich</th>}
                  {r && <th className="py-2 font-semibold">Ergebnis</th>}
                </tr>
              </thead>
              <tbody>
                {r
                  ? r.results.map((s) => (
                      <tr key={s.scenario_id} className="border-b border-line align-top last:border-0">
                        <td className="py-2.5 pr-3">
                          <div className="font-medium">{s.title_de}</div>
                          <div className="font-mono text-[11.5px] text-ink-subtle">{s.scenario_id}</div>
                          {s.actual_rule_ids.length > 0 && (
                            <div className="mt-1 font-mono text-[11px] text-ink-subtle">Regeln: {s.actual_rule_ids.join(", ")}</div>
                          )}
                        </td>
                        <td className="py-2.5 pr-3">
                          <Badge tone={VALIDATION[s.validation as keyof typeof VALIDATION]?.tone ?? "neutral"}>
                            {VALIDATION[s.validation as keyof typeof VALIDATION]?.label ?? s.validation}
                          </Badge>
                        </td>
                        <td className="py-2.5 pr-3">
                          <ActionBadge action={s.expected_action as Action} />
                        </td>
                        <td className="py-2.5 pr-3">
                          <ActionBadge action={s.actual_action as Action} />
                        </td>
                        <td className="py-2.5">
                          {s.passed ? (
                            <Badge tone="proceed" icon={CircleCheck}>
                              Bestanden
                            </Badge>
                          ) : (
                            <div>
                              <Badge tone="error" icon={CircleX}>
                                Fehlgeschlagen
                              </Badge>
                              <ul className="mt-1.5 list-disc pl-4 text-[12px] text-error-fg">
                                {s.mismatches.map((m) => (
                                  <li key={m}>{m}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))
                  : (scenarios.data ?? []).map((s) => (
                      <tr key={s.id} className="border-b border-line last:border-0">
                        <td className="py-2.5 pr-3">
                          <div className="font-medium">{s.title_de}</div>
                          <div className="font-mono text-[11.5px] text-ink-subtle">{s.id}</div>
                        </td>
                        <td className="py-2.5 pr-3">
                          <Badge tone={VALIDATION[s.validation as keyof typeof VALIDATION]?.tone ?? "neutral"}>
                            {VALIDATION[s.validation as keyof typeof VALIDATION]?.label ?? s.validation}
                          </Badge>
                        </td>
                        <td className="py-2.5 pr-3">
                          <ActionBadge action={s.expected_action as Action} />
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
