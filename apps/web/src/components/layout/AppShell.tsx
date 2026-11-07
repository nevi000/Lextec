import { FolderOpen, Plus, TriangleAlert, Wrench } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useCreateCase, useSystemStatus } from "@/lib/queries";

export function NewCaseButton({
  size = "md",
  variant = "accent",
  label = "Neuen Fall erfassen",
  className,
}: {
  size?: "sm" | "md" | "lg";
  variant?: "accent" | "primary" | "secondary";
  label?: string;
  className?: string;
}) {
  const navigate = useNavigate();
  const create = useCreateCase((id) => navigate(`/cases/${id}`));
  return (
    <Button size={size} variant={variant} className={className} loading={create.isPending} onClick={() => create.mutate()}>
      <Plus /> {label}
    </Button>
  );
}

function navClass({ isActive }: { isActive: boolean }) {
  return cn(
    "group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13.5px] font-medium transition-colors",
    isActive ? "bg-white/10 text-white" : "text-brand-200 hover:bg-white/5 hover:text-white",
  );
}

/** Honest, compact privacy notice: external AI processing is never hidden. Cost details live in the developer area. */
function SystemNotice() {
  const { data, isError } = useSystemStatus();
  if (isError) {
    return (
      <div className="flex items-center gap-2 rounded-md bg-escalate-bg/90 px-2.5 py-2 text-[12px] text-escalate-fg">
        <TriangleAlert className="size-3.5" aria-hidden /> Backend nicht erreichbar
      </div>
    );
  }
  if (!data) return null;
  return (
    <div className="space-y-1.5 text-[11.5px] leading-snug text-brand-200" title={data.notice}>
      <div className="flex items-start gap-1.5">
        <span
          className={cn("mt-1 size-1.5 shrink-0 rounded-full", data.ai_is_external ? "bg-escalate-solid" : "bg-brand-500")}
          aria-hidden
        />
        {data.ai_is_external
          ? "Texte werden zur Auswertung an eine externe KI (Gemini) gesendet."
          : "KI-Auswertung lokal simuliert, keine Daten verlassen den Rechner."}
      </div>
      <div className="opacity-80">Lokaler Prototyp · nur synthetische Daten verwenden</div>
      {data.app_env === "development" && (
        <NavLink to="/dev" className="inline-flex items-center gap-1 pt-1 text-brand-300 underline-offset-2 hover:underline">
          <Wrench className="size-3" aria-hidden /> Entwicklerbereich
        </NavLink>
      )}
    </div>
  );
}

export function AppShell() {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="no-print bg-brand-900 text-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <div className="flex items-center justify-between gap-3 px-4 py-4 lg:px-5 lg:py-5">
          <NavLink to="/" aria-label="LexTec Bridge, zu Meine Fälle" className="block leading-none">
            {/* Official LexTec wordmark (white), served locally from /public/brand */}
            <img src="/brand/lextec-logo-white.png" alt="LexTec" width={1888} height={446} className="h-9 w-auto" />
            <span className="mt-0.5 block pl-0.5 font-display text-[12.5px] font-semibold tracking-wide text-brand-300">Bridge</span>
          </NavLink>
          <nav aria-label="Hauptnavigation" className="flex items-center gap-1 lg:hidden">
            <NavLink to="/" end className={navClass}>
              <FolderOpen className="size-4 shrink-0" aria-hidden /> Meine Fälle
            </NavLink>
          </nav>
        </div>
        <nav aria-label="Hauptnavigation" className="hidden gap-1 px-3 lg:flex lg:flex-1 lg:flex-col">
          <div className="mb-2 px-1">
            <NewCaseButton className="w-full" />
          </div>
          <NavLink to="/" end className={navClass}>
            <FolderOpen className="size-4 shrink-0" aria-hidden />
            <span className="whitespace-nowrap">Meine Fälle</span>
          </NavLink>
        </nav>
        <div className="hidden border-t border-white/10 p-4 lg:block">
          <SystemNotice />
        </div>
      </aside>
      <main className="min-w-0">
        <div className="print-shell mx-auto w-full max-w-[1100px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
