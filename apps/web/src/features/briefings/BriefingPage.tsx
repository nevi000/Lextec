import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Download, ExternalLink, FileText, RefreshCw } from "lucide-react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Badge } from "@/components/shared/badges";
import { EmptyState, ErrorState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { errorMessage, useBriefing, useBriefings, useCase, useInvalidateCase } from "@/lib/queries";
import { formatDateTime } from "@/lib/utils";
import { BriefingDocument } from "./BriefingDocument";

export function BriefingPage() {
  const { caseId = "", briefingId } = useParams();
  const navigate = useNavigate();
  const caseQ = useCase(caseId);
  const listQ = useBriefings(caseId);
  const viewQ = useBriefing(caseId, briefingId);
  const invalidate = useInvalidateCase(caseId);

  const create = useMutation({
    mutationFn: () => api.createBriefing(caseId),
    onSuccess: (b) => {
      void invalidate();
      toast.success(`Fallbericht (Version ${b.version}) erstellt`);
      navigate(`/cases/${caseId}/briefing/${b.id}`, { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (caseQ.isError) return <ErrorState error={caseQ.error} onRetry={() => void caseQ.refetch()} />;
  if (listQ.isError) return <ErrorState error={listQ.error} onRetry={() => void listQ.refetch()} />;
  if (!caseQ.data || !listQ.data) return <Skeleton className="h-96" />;

  const detail = caseQ.data;
  const versions = listQ.data;

  if (!briefingId && versions.length > 0 && versions[0]) {
    return <Navigate to={`/cases/${caseId}/briefing/${versions[0].id}`} replace />;
  }

  const isLatest = versions[0]?.id === briefingId;
  const stale = isLatest && detail.briefing_stale;

  return (
    <div>
      <div className="no-print mb-5 flex flex-wrap items-center justify-between gap-3">
        <Link to={`/cases/${caseId}`} className="inline-flex items-center gap-1 text-[12.5px] text-ink-subtle hover:text-ink">
          <ArrowLeft className="size-3.5" aria-hidden /> Zurück zum Fall · {detail.title}
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          {versions.length > 0 && (
            <Select
              aria-label="Briefing-Version"
              className="w-auto"
              value={briefingId ?? ""}
              onChange={(e) => navigate(`/cases/${caseId}/briefing/${e.target.value}`)}
            >
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  Version {v.version} · {formatDateTime(v.created_at)}
                </option>
              ))}
            </Select>
          )}
          {versions.length > 0 && (
            <Button variant="secondary" size="sm" loading={create.isPending} onClick={() => create.mutate()}>
              <RefreshCw /> Fallbericht aktualisieren
            </Button>
          )}
          {briefingId && (
            <Button asChild variant="primary" size="sm">
              <a href={`/api/cases/${caseId}/briefings/${briefingId}/pdf`} download>
                <Download /> PDF herunterladen
              </a>
            </Button>
          )}
        </div>
      </div>

      {stale && (
        <div role="status" className="no-print mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-ask-line bg-ask-bg px-4 py-3 text-[13px] text-ask-fg">
          <Badge tone="ask">Nicht aktuell</Badge>
          Der Fall wurde seit dieser Version geändert. Mit «Fallbericht aktualisieren» entsteht eine neue Version mit dem aktuellen Stand; die älteren Versionen bleiben erhalten.
        </div>
      )}
      {!isLatest && briefingId && (
        <div role="status" className="no-print mb-4 rounded-lg border border-line bg-sunken px-4 py-3 text-[13px] text-ink-muted">
          Sie sehen eine ältere Version.
        </div>
      )}

      {!briefingId && (
        <EmptyState
          icon={FileText}
          title="Noch kein Fallbericht erstellt"
          description="Das Briefing wird aus dem gespeicherten Fallstand erzeugt: Fakten, offene Punkte, Entscheidung und Rechtsquellen."
          action={
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>
              <FileText /> Fallbericht erstellen
            </Button>
          }
        />
      )}
      {briefingId && (
        <>
          <p className="no-print mb-2 text-[12px] text-ink-subtle">
            A4-Vorschau des Fallberichts (Version {viewQ.data?.version ?? ""}). Das PDF enthält Seitenzahlen und Fusszeile.{" "}
            <a
              className="inline-flex items-center gap-1 text-brand-700 underline"
              href={`/api/cases/${caseId}/briefings/${briefingId}/preview`}
              target="_blank"
              rel="noreferrer"
            >
              In neuem Tab öffnen und drucken <ExternalLink className="size-3" aria-hidden />
            </a>
          </p>
          <iframe
            title="Fallbericht-Vorschau"
            src={`/api/cases/${caseId}/briefings/${briefingId}/preview`}
            sandbox="allow-popups allow-popups-to-escape-sandbox"
            className="no-print h-[calc(100vh-11rem)] min-h-[640px] w-full rounded-lg border border-line bg-white"
          />
        </>
      )}
      {viewQ.isLoading && <Skeleton className="h-24" />}
      {viewQ.isError && <ErrorState error={viewQ.error} onRetry={() => void viewQ.refetch()} />}
      {viewQ.data && (
        <details className="no-print mt-4 rounded-lg border border-line bg-surface">
          <summary className="cursor-pointer px-4 py-3 text-[13px] font-medium">Frühere Detailansicht (technisch)</summary>
          <div className="p-4">
            <BriefingDocument view={viewQ.data} />
          </div>
        </details>
      )}
    </div>
  );
}
