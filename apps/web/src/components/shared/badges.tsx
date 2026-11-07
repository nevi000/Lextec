import {
  BadgeCheck,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  Clock3,
  MessageCircleQuestionMark,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Action, FactOrigin, FactStatus, HandoverStatus } from "@/types";

export type Tone =
  | "neutral"
  | "brand"
  | "ask"
  | "proceed"
  | "escalate"
  | "warning"
  | "error"
  | "unverified"
  | "incomplete";

const tones: Record<Tone, string> = {
  neutral: "bg-sunken text-ink-muted border-line",
  brand: "bg-brand-100 text-brand-800 border-brand-200",
  ask: "bg-ask-bg text-ask-fg border-ask-line",
  proceed: "bg-proceed-bg text-proceed-fg border-proceed-line",
  escalate: "bg-escalate-bg text-escalate-fg border-escalate-line",
  warning: "bg-warning-bg text-warning-fg border-ask-line",
  error: "bg-error-bg text-error-fg border-error-line",
  unverified: "bg-unverified-bg text-unverified-fg border-unverified-line",
  incomplete: "bg-incomplete-bg text-incomplete-fg border-incomplete-line",
};

export function Badge({
  tone = "neutral",
  icon: Icon,
  children,
  className,
  title,
}: {
  tone?: Tone;
  icon?: LucideIcon;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-2 py-0.5 text-[11.5px] font-medium leading-5",
        tones[tone],
        className,
      )}
    >
      {Icon && <Icon className="size-3.5 shrink-0" aria-hidden />}
      {children}
    </span>
  );
}

export const ACTION_META: Record<Action, { label: string; tone: Tone; icon: LucideIcon; verb: string }> = {
  ASK: { label: "Rückfrage nötig", tone: "ask", icon: MessageCircleQuestionMark, verb: "ASK" },
  PROCEED: { label: "Weiter bearbeiten", tone: "proceed", icon: CircleCheck, verb: "PROCEED" },
  ESCALATE: { label: "Fachperson nötig", tone: "escalate", icon: TriangleAlert, verb: "ESCALATE" },
};

export function ActionBadge({ action, withCode = false }: { action: Action | null | undefined; withCode?: boolean }) {
  if (!action) {
    return (
      <Badge tone="neutral" icon={CircleDashed}>
        Noch keine Einschätzung
      </Badge>
    );
  }
  const m = ACTION_META[action];
  return (
    <Badge tone={m.tone} icon={m.icon} title={m.verb}>
      {m.label}
      {withCode && <span className="font-mono text-[10.5px] opacity-70">{m.verb}</span>}
    </Badge>
  );
}

const FACT_STATUS: Record<FactStatus, { label: string; tone: Tone }> = {
  KNOWN: { label: "Bekannt", tone: "proceed" },
  MISSING: { label: "Fehlt", tone: "incomplete" },
  AMBIGUOUS: { label: "Unklar", tone: "ask" },
  CONTRADICTORY: { label: "Widersprüchlich", tone: "escalate" },
  NOT_APPLICABLE: { label: "Nicht zutreffend", tone: "neutral" },
  UNKNOWN: { label: "Unbekannt (gefragt)", tone: "unverified" },
};

export function FactStatusBadge({ status }: { status: FactStatus }) {
  const m = FACT_STATUS[status];
  return <Badge tone={m.tone}>{m.label}</Badge>;
}

export const ORIGIN_LABEL: Record<FactOrigin, string> = {
  AI_EXTRACTED: "Aus Schilderung (KI)",
  USER_ANSWER: "Antwort erfasst",
  USER_CORRECTION: "Von Ihnen korrigiert",
};

export function ProvenanceBadge({ origin, confirmed }: { origin: FactOrigin | null | undefined; confirmed?: boolean }) {
  if (!origin) return null;
  return (
    <span className="inline-flex items-center gap-1.5">
      <Badge tone={origin === "AI_EXTRACTED" ? "unverified" : "brand"}>{ORIGIN_LABEL[origin]}</Badge>
      {confirmed && (
        <Badge tone="proceed" icon={BadgeCheck}>
          Bestätigt
        </Badge>
      )}
    </span>
  );
}

export const URGENCY_LABEL: Record<"HIGH" | "MEDIUM" | "LOW", string> = {
  HIGH: "sofort",
  MEDIUM: "bald",
  LOW: "normal",
};

/** Dringlichkeit laut Law-Dossier: sofort / bald / normal. Interne Einschätzung, kein Fristende. */
export function UrgencyBadge({ urgency }: { urgency: "HIGH" | "MEDIUM" | "LOW" | null | undefined }) {
  if (!urgency) return null;
  const tone: Tone = urgency === "HIGH" ? "escalate" : urgency === "MEDIUM" ? "ask" : "neutral";
  return (
    <Badge tone={tone} icon={Clock3} title="Interne Dringlichkeit (Produktregel), kein Fristende">
      Dringlichkeit: {URGENCY_LABEL[urgency]}
    </Badge>
  );
}

export const EVIDENCE_META: Record<string, { label: string; tone: Tone }> = {
  DOCUMENTED: { label: "Dokumentarisch belegt", tone: "proceed" },
  CONFIRMED: { label: "Von Sozialarbeiterin bestätigt", tone: "proceed" },
  STATED: { label: "Vom Nutzer angegeben", tone: "brand" },
  AI_EXTRACTED: { label: "Von KI extrahiert", tone: "unverified" },
  SYSTEM_DERIVED: { label: "Systemseitig abgeleitet", tone: "neutral" },
  UNKNOWN: { label: "Gefragt, unbekannt", tone: "ask" },
  UNCLEAR: { label: "Unklar / widersprüchlich", tone: "escalate" },
  NOT_ASKED: { label: "Noch ungeklärt", tone: "incomplete" },
};

export function EvidenceBadge({ level }: { level: string }) {
  const m = EVIDENCE_META[level] ?? { label: level, tone: "neutral" as Tone };
  return <Badge tone={m.tone}>{m.label}</Badge>;
}

/** What the law team's dossier says about a source - NOT a verification by this system. */
export function DossierBadge({ status }: { status: string }) {
  if (status === "DOSSIER_CHECKED")
    return (
      <Badge tone="brand" title="Im Law-Dossier gegen Volltext/PDF geprüft (keine Systemprüfung)">
        Im Law-Dossier geprüft
      </Badge>
    );
  if (status === "REFERENCED_ONLY") return <Badge tone="neutral">Nur erwähnt, ohne Wortlaut</Badge>;
  return <Badge tone="incomplete">Dossier: noch nicht geprüft</Badge>;
}

export function VerificationBadge({ status }: { status: "VERIFIED" | "UNVERIFIED" | "FAILED" }) {
  if (status === "VERIFIED")
    return (
      <Badge tone="proceed" icon={BadgeCheck}>
        Verifiziert
      </Badge>
    );
  if (status === "FAILED")
    return (
      <Badge tone="error" icon={CircleAlert}>
        Prüfung fehlgeschlagen
      </Badge>
    );
  return (
    <Badge tone="unverified" icon={CircleDashed} title="Fedlex/BGer sind nicht angebunden; das System hat die Quelle nicht live geprüft">
      Vom System nicht live verifiziert
    </Badge>
  );
}

const HANDOVER: Record<HandoverStatus, { label: string; tone: Tone }> = {
  RECOMMENDED: { label: "Übergabe empfohlen", tone: "ask" },
  HANDOFF_REQUESTED: { label: "Übergabe angefragt", tone: "brand" },
  HANDOFF_COMPLETED: { label: "Übergabe bestätigt", tone: "proceed" },
};

export function HandoverBadge({ status }: { status: HandoverStatus | null | undefined }) {
  if (!status) return null;
  const m = HANDOVER[status];
  return <Badge tone={m.tone}>{m.label}</Badge>;
}
