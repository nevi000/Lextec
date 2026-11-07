import { useMutation } from "@tanstack/react-query";
import { ArrowRight, FlaskConical } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Badge } from "@/components/shared/badges";
import { PageHeader } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { errorMessage, useSystemStatus } from "@/lib/queries";
import { DEMO_STEPS, DEMO_TITLE } from "./demoScenario";

export function DemoPage() {
  const navigate = useNavigate();
  const { data: status } = useSystemStatus();
  const start = useMutation({
    mutationFn: () => api.createCase(DEMO_TITLE),
    onSuccess: (c) => {
      toast.success(`${c.display_id} angelegt (synthetische Demo-Daten)`);
      navigate(`/cases/${c.id}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const gemini = status?.ai_is_external;
  const usage = status?.ai_usage;

  return (
    <>
      <PageHeader
        title="Demo: Mietkündigung Zürich"
        description="Eine Sozialarbeiterin betreut eine verunsicherte Mieterin, die eine Kündigung erhalten hat. Sie durchlaufen den echten Ablauf: Rückfragen, Eskalationsentscheid mit Regeln und das Expert Briefing."
        actions={
          <Button size="lg" variant="accent" loading={start.isPending} onClick={() => start.mutate()}>
            <FlaskConical /> Demo starten
          </Button>
        }
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader>
            <CardTitle>Ablauf in fünf Schritten</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-3">
              {DEMO_STEPS.map((s) => (
                <li key={s.id} className="flex gap-3">
                  <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-brand-900 text-[12px] font-semibold text-white">
                    {s.id}
                  </span>
                  <div>
                    <p className="text-[13.5px] font-medium">
                      {s.title} {s.optional && <Badge tone="neutral">optional</Badge>}
                    </p>
                    <ul className="mt-0.5 list-disc pl-5 text-[12.5px] text-ink-muted">
                      {s.expect.slice(0, 2).map((e) => (
                        <li key={e}>{e}</li>
                      ))}
                    </ul>
                  </div>
                </li>
              ))}
            </ol>
            <Button className="mt-5" variant="primary" loading={start.isPending} onClick={() => start.mutate()}>
              Demo starten <ArrowRight />
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Betriebsmodus</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[13px] text-ink-muted">
              <div>
                {gemini ? (
                  <Badge tone="escalate">Gemini (extern) · {status?.ai_model}</Badge>
                ) : (
                  <Badge tone="brand">Mock (lokal, simuliert)</Badge>
                )}
              </div>
              {gemini ? (
                <p>
                  Die Beispieltexte werden an die Gemini-API übermittelt (synthetisch). Pro Demo sind etwa 3 bis 5
                  KI-Aufrufe zu erwarten; einfache Antworten wie «Ja» oder ein Datum werden lokal verarbeitet.
                  {usage && (
                    <>
                      {" "}
                      Heute bisher: {usage.calls_today} Aufrufe
                      {usage.estimated_cost_today_usd != null && `, geschätzt $${usage.estimated_cost_today_usd.toFixed(4)}`} (Limit{" "}
                      {usage.daily_request_limit} Aufrufe, ${usage.daily_budget_usd.toFixed(2)} pro Tag; Anwendungslimits,
                      keine garantierte Abrechnungsgrenze).
                    </>
                  )}
                </p>
              ) : (
                <p>Es werden keine Daten an externe Dienste gesendet. Für echte Sprachauswertung <code>AI_PROVIDER=gemini</code> setzen.</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Wichtig</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[12.5px] text-ink-muted">
              <p>Alle Daten sind synthetisch. Die rechtlichen Inhalte stammen aus dem Law-Dossier vom 7.11.2026 und sind noch nicht für den Einsatz mit echten Klienten freigegeben.</p>
              <p>Das System gibt keine Rechtsauskunft, berechnet kein Fristende und beurteilt nicht, ob eine Kündigung gültig ist.</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
