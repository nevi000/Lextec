import { Database, FileText, FlaskConical, Play, Settings, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/shared/states";
import { Card } from "@/components/ui/card";
import { DEMO_TITLE } from "@/features/demo/demoScenario";

const ITEMS: { to: string; label: string; text: string; icon: LucideIcon }[] = [
  { to: "/knowledge-base", label: "Knowledge Base", text: "Issues, Regeln, Rechtsquellen und Fedlex-Status.", icon: Database },
  { to: "/evaluation", label: "Evaluation", text: "Szenario-Tests der Entscheidungslogik.", icon: FlaskConical },
  { to: "/briefings", label: "Alle Expert Briefings", text: "Verzeichnis aller erstellten Briefings.", icon: FileText },
  { to: "/settings", label: "Einstellungen & KI-Nutzung", text: "Modell, Datenschutzstatus, Aufrufe und Kostenlimits.", icon: Settings },
  { to: "/demo", label: "Geführte Demo", text: `Legt einen Fall «${DEMO_TITLE}» mit Beispieltexten an.`, icon: Play },
];

/** Local developer / QA area. Not part of the social worker's navigation; no extra auth system. */
export function DevPage() {
  return (
    <>
      <PageHeader
        title="Entwicklerbereich"
        description="Werkzeuge für Entwicklung und Qualitätssicherung. Nicht Teil des normalen Arbeitsablaufs."
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {ITEMS.map(({ to, label, text, icon: Icon }) => (
          <Link key={to} to={to} className="rounded-lg focus-visible:outline-offset-2">
            <Card className="h-full p-4 transition-colors hover:bg-brand-50">
              <div className="flex items-center gap-2 font-medium">
                <Icon className="size-4 text-brand-600" aria-hidden /> {label}
              </div>
              <p className="mt-1 text-[13px] text-ink-muted">{text}</p>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
