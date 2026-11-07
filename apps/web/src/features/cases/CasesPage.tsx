import { FolderOpen, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { NewCaseButton } from "@/components/layout/AppShell";
import { EmptyState, ErrorState, PageHeader } from "@/components/shared/states";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { CaseList } from "@/features/cases/CaseList";
import { caseStatus } from "@/lib/caseStatus";
import { useCases } from "@/lib/queries";
import { cn } from "@/lib/utils";

const FILTERS = [
  { id: "all", label: "Alle" },
  { id: "active", label: "In Bearbeitung" },
  { id: "handover", label: "Übergabe" },
  { id: "closed", label: "Abgeschlossen" },
] as const;
type FilterId = (typeof FILTERS)[number]["id"];

export function CasesPage() {
  const [filter, setFilter] = useState<FilterId>("all");
  const [text, setText] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setQ(text), 250);
    return () => clearTimeout(t);
  }, [text]);

  const { data, isLoading, isError, error, refetch, isFetching } = useCases({ q, status: "", action: "", sort: "updated_desc" });
  const shown = (data ?? []).filter((c) => filter === "all" || caseStatus(c).group === filter);
  const filtered = !!q || filter !== "all";

  return (
    <>
      <PageHeader
        title="Meine Fälle"
        description="Hier finden Sie Ihre erfassten Beratungsfälle."
        actions={<NewCaseButton size="lg" />}
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-subtle" aria-hidden />
          <Input
            aria-label="Fälle durchsuchen"
            placeholder="Fall suchen …"
            className="pl-9"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <div role="group" aria-label="Fälle filtern" className="flex gap-1 rounded-lg bg-sunken p-1">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}
              className={cn(
                "rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors",
                filter === f.id ? "bg-surface text-ink shadow-xs" : "text-ink-muted hover:text-ink",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {isError && <ErrorState error={error} onRetry={() => void refetch()} />}
      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      )}
      {data && shown.length > 0 && (
        <div className={isFetching ? "opacity-70 transition-opacity" : "transition-opacity"}>
          <CaseList cases={shown} />
        </div>
      )}
      {data && shown.length === 0 && (
        <EmptyState
          icon={FolderOpen}
          title={filtered ? "Keine passenden Fälle" : "Noch keine Fälle erfasst"}
          description={
            filtered
              ? "Passen Sie Suche oder Filter an."
              : "Erfassen Sie Ihren ersten Fall: Beschreiben Sie die Situation in eigenen Worten."
          }
          action={filtered ? undefined : <NewCaseButton />}
        />
      )}
    </>
  );
}
