import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { Link } from "react-router-dom";
import { ActionBadge } from "@/components/shared/badges";
import { EmptyState, ErrorState, PageHeader } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";
import { formatDateTime } from "@/lib/utils";

export function BriefingOverviewPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: keys.briefingOverview,
    queryFn: api.briefingOverview,
  });
  return (
    <>
      <PageHeader
        title="Expert Briefings"
        description="Strukturierte Übergabeberichte pro Fall. Jede Aktualisierung erzeugt eine neue Version; ältere bleiben erhalten."
      />
      {isError && <ErrorState error={error} onRetry={() => void refetch()} />}
      {isLoading && <Skeleton className="h-48" />}
      {data && data.length === 0 && (
        <EmptyState icon={FileText} title="Noch keine Fälle" description="Briefings entstehen aus erfassten Fällen." />
      )}
      {data && data.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-ink-subtle">
                <th className="px-5 py-2.5 font-semibold">Fall</th>
                <th className="px-3 py-2.5 font-semibold">Einschätzung</th>
                <th className="px-3 py-2.5 font-semibold">Neueste Version</th>
                <th className="px-5 py-2.5 text-right font-semibold" />
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.case.id} className="border-b border-line last:border-0 hover:bg-brand-50">
                  <td className="px-5 py-3">
                    <span className="font-mono text-[12px] text-ink-subtle">{r.case.display_id}</span>
                    <span className="block font-medium">{r.case.title}</span>
                  </td>
                  <td className="px-3 py-3">
                    <ActionBadge action={r.case.current_action} />
                  </td>
                  <td className="px-3 py-3 text-ink-muted">
                    {r.latest_version ? (
                      <>
                        Version {r.latest_version} · {formatDateTime(r.latest_created_at)}
                        <span className="text-ink-subtle"> ({r.briefing_count} insgesamt)</span>
                      </>
                    ) : (
                      "Noch kein Briefing"
                    )}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Button asChild variant="secondary" size="sm">
                      <Link to={`/cases/${r.case.id}/briefing`}>{r.latest_version ? "Öffnen" : "Erstellen"}</Link>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
