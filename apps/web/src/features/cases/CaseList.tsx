import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/shared/badges";
import { caseStatus } from "@/lib/caseStatus";
import { formatDateTime, relativeTime } from "@/lib/utils";
import type { CaseListItem } from "@/types";

/** Calm case list: title, problem type, last update, plain-language status. No codes, no AI metrics. */
export function CaseList({ cases }: { cases: CaseListItem[] }) {
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      {cases.map((c) => {
        const st = caseStatus(c); // includes issue_titles: "Noch nicht gestartet" before the first analysis
        return (
          <li key={c.id}>
            <Link
              to={`/cases/${c.id}`}
              className="group flex items-center gap-4 px-4 py-3.5 hover:bg-brand-50 focus-visible:outline-offset-[-2px] sm:px-5"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-ink group-hover:text-brand-700">{c.title}</p>
                <p className="mt-0.5 truncate text-[12.5px] text-ink-muted">
                  {c.issue_titles.length ? c.issue_titles.join(" · ") : "Problemtyp noch nicht erkannt"}
                  <span className="text-ink-subtle" title={formatDateTime(c.updated_at)}>
                    {" "}
                    · {relativeTime(c.updated_at)}
                  </span>
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                <Badge tone={st.tone === "brand" ? "brand" : st.tone}>{st.label}</Badge>
                {c.analysis_pending && <Badge tone="warning">Analyse ausstehend</Badge>}
              </div>
              <ChevronRight className="size-4 shrink-0 text-ink-subtle" aria-hidden />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
