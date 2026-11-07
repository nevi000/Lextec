import { ListChecks, Scale } from "lucide-react";
import { Badge } from "@/components/shared/badges";
import { Button } from "@/components/ui/button";
import type { CaseDetail, FactView } from "@/types";

/**
 * Compact «what does the system know» strip: recognised problem(s), a short neutral summary and the entry to all
 * case information. No confidence scores, no codes, no fact lists.
 */
export function CaseSummary({
  detail,
  facts,
  onOpenAll,
}: {
  detail: CaseDetail;
  facts: FactView[];
  onOpenAll: () => void;
}) {
  const unsupported = detail.issues.filter((i) => i.classification_status === "UNSUPPORTED");
  const supported = detail.issues.filter((i) => i.classification_status !== "UNSUPPORTED");
  const unclear = facts.filter((f) => f.status === "AMBIGUOUS" || f.status === "CONTRADICTORY").length;

  return (
    <section aria-label="Dieser Fall" className="rounded-xl border border-line bg-surface p-5 shadow-card sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11.5px] font-semibold uppercase tracking-wider text-ink-subtle">
            {supported.length > 0 && unsupported.length > 0 ? "Erkanntes Mietrechtsproblem" : "Erkanntes Problem"}
          </p>
          {supported.length === 0 && unsupported.length === 0 ? (
            <p className="mt-1 text-[14px] text-ink-muted">Das Rechtsproblem ist noch nicht eindeutig erkannt.</p>
          ) : (
            <>
              {supported.length > 0 && (
                <ul className="mt-1 flex flex-wrap gap-2">
                  {supported.map((i) => (
                    <li key={i.id}>
                      <Badge tone="brand" icon={Scale}>
                        {i.title_de ?? i.description}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
              {unsupported.length > 0 && (
                <>
                  {supported.length > 0 && <p className="mt-3 text-[12px] font-semibold text-ink-subtle">Weiteres erkanntes Rechtsgebiet</p>}
                  <ul className="mt-1 flex flex-wrap gap-2">
                    {unsupported.map((i) => (
                      <li key={i.id}>
                        <Badge tone="escalate">{i.title_de ?? i.description} – nicht abgedeckt</Badge>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </div>
        <Button variant="secondary" size="sm" onClick={onOpenAll}>
          <ListChecks /> Alle Fallinformationen
        </Button>
      </div>
      {unsupported.length > 0 && (
        <p className="mt-2 text-[13px] text-ink-muted" data-testid="unsupported-note">
          {supported.length > 0
            ? `Der Fall enthält auch eine weitere Rechtsfrage (${unsupported.map((i) => i.title_de ?? i.description).join(", ")}). Dieses Rechtsgebiet wird von LexTec Bridge nicht geprüft. Eine entsprechende Fachperson sollte diesen Teil beurteilen.`
            : "LexTec Bridge unterstützt dieses Rechtsgebiet derzeit nicht. Bitte lassen Sie den Fall durch eine entsprechende Fachperson beurteilen."}
        </p>
      )}
      {detail.summary && <p className="mt-3 text-[13.5px] leading-relaxed text-ink-muted">{detail.summary}</p>}
      {(unclear > 0 || detail.summary) && (
        <p className="mt-2 text-[12px] text-ink-subtle">
          {detail.summary && "Zusammenfassung von der KI erstellt, bitte prüfen."}
          {unclear > 0 && ` ${unclear} Angabe(n) sind unklar oder widersprüchlich.`}
        </p>
      )}
    </section>
  );
}
