import { Link } from "react-router-dom";
import { Badge } from "@/components/shared/badges";
import { ErrorState, PageHeader } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAIUsage, useSystemStatus } from "@/lib/queries";
import { formatDateTime } from "@/lib/utils";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line py-2.5 last:border-0">
      <dt className="text-[13px] text-ink-muted">{label}</dt>
      <dd className="text-[13px] font-medium">{children}</dd>
    </div>
  );
}

function UsageCard() {
  const { data } = useAIUsage();
  if (!data) return null;
  const s = data.summary;
  return (
    <Card className="lg:col-span-2" data-testid="ai-usage">
      <CardHeader>
        <CardTitle>KI-Verbrauch (Gemini)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-3 text-[13px] sm:grid-cols-4">
          <div>
            <dt className="text-ink-muted">Aufrufe heute</dt>
            <dd className="text-lg font-semibold tabular-nums">
              {s.calls_today} / {s.daily_request_limit}
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Geschätzte Kosten heute</dt>
            <dd className="text-lg font-semibold tabular-nums">
              {s.estimated_cost_today_usd != null ? `$${s.estimated_cost_today_usd.toFixed(4)}` : "unbekannt"}
              <span className="text-[12px] font-normal text-ink-subtle"> / ${s.daily_budget_usd.toFixed(2)}</span>
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Tokens heute (ein / aus)</dt>
            <dd className="text-lg font-semibold tabular-nums">
              {s.input_tokens_today} / {s.output_tokens_today}
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Blockiert (Limit)</dt>
            <dd className="text-lg font-semibold tabular-nums">{s.blocked_today}</dd>
          </div>
        </dl>
        <p className="text-[12px] text-ink-subtle">
          Das sind <strong>Anwendungslimits</strong> mit eigener Zählung und geschätzten Preisen, keine garantierte
          Abrechnungsgrenze bei Google. Pro Fall höchstens {s.max_calls_per_case} Aufrufe und ${s.case_budget_usd.toFixed(2)}.
          Einfache Antworten (Ja/Nein, Datum, Auswahl) werden lokal verarbeitet und kosten nichts.
        </p>
        {data.recent.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-left text-[12px]">
              <thead>
                <tr className="border-b border-line text-ink-subtle">
                  <th className="py-1.5 pr-3 font-medium">Zeit</th>
                  <th className="py-1.5 pr-3 font-medium">Funktion</th>
                  <th className="py-1.5 pr-3 font-medium">Status</th>
                  <th className="py-1.5 pr-3 font-medium">Tokens ein/aus/denken</th>
                  <th className="py-1.5 font-medium">Kosten</th>
                </tr>
              </thead>
              <tbody>
                {data.recent.map((r, i) => (
                  <tr key={i} className="border-b border-line last:border-0">
                    <td className="py-1.5 pr-3">{formatDateTime(r.created_at)}</td>
                    <td className="py-1.5 pr-3">{r.function}</td>
                    <td className="py-1.5 pr-3">
                      {r.status}
                      {r.error_code && <span className="text-ink-subtle"> ({r.error_code})</span>}
                    </td>
                    <td className="py-1.5 pr-3 tabular-nums">
                      {r.input_tokens} / {r.output_tokens} / {r.thinking_tokens}
                    </td>
                    <td className="py-1.5 tabular-nums">{r.cost_usd != null ? `$${r.cost_usd.toFixed(5)}` : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function SettingsPage() {
  const { data, isLoading, isError, error, refetch } = useSystemStatus();
  return (
    <>
      <PageHeader
        title="Einstellungen"
        description="Konfiguration erfolgt über die .env-Datei im Projektstamm. Diese Seite zeigt den aktuellen Betriebsmodus."
      />
      {isError && <ErrorState error={error} onRetry={() => void refetch()} />}
      {isLoading && <Skeleton className="h-64" />}
      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Betriebsmodus</CardTitle>
            </CardHeader>
            <CardContent>
              <dl>
                <Row label="Umgebung">{data.app_env}</Row>
                <Row label="Authentifizierung">
                  <Badge tone="warning">Keine – lokaler Demo-Modus</Badge>
                </Row>
                <Row label="KI-Anbieter">
                  {data.ai_provider === "gemini" ? (
                    <Badge tone="escalate">Gemini (extern)</Badge>
                  ) : (
                    <Badge tone="brand">Mock (lokal)</Badge>
                  )}
                </Row>
                <Row label="Modell">
                  <span className="font-mono text-[12px]">{data.ai_model}</span>
                </Row>
                <Row label="Knowledge-Base-Version">
                  <span className="font-mono text-[12px]">{data.knowledge_base_version}</span>
                </Row>
                <Row label="Knowledge Base gültig">{data.knowledge_base_valid ? "Ja" : "Nein – siehe Knowledge Base"}</Row>
              </dl>
              <Button asChild variant="secondary" size="sm" className="mt-4">
                <Link to="/knowledge-base">Knowledge Base ansehen</Link>
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Datenschutz-Hinweis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-[13px] text-ink-muted">
              <p>{data.notice}</p>
              <p>
                Verwenden Sie ausschliesslich <strong className="text-ink">synthetische Daten</strong>. Echte
                Klientendaten dürfen erst nach Datenschutz-, Vertrags- und Zugriffsprüfung (revDSG) erfasst werden.
              </p>
              <p>
                Im Gemini-Modus werden Gesprächstexte an die Google-Gemini-API übermittelt. Im Mock-Modus verlässt
                nichts den lokalen Rechner.
              </p>
            </CardContent>
          </Card>
          {data.ai_is_external && <UsageCard />}
        </div>
      )}
    </>
  );
}

export function NotFoundPage() {
  return (
    <div className="py-20 text-center">
      <p className="text-[13px] text-ink-subtle">404</p>
      <h1 className="mt-1 text-xl font-semibold">Seite nicht gefunden</h1>
      <Button asChild variant="secondary" className="mt-5">
        <Link to="/">Zur Übersicht</Link>
      </Button>
    </div>
  );
}
