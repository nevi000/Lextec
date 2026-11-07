import type { CaseDetail, CaseListItem } from "@/types";

/** Plain-language case status for social workers. Derived only from backend state; no codes. */
export type StatusTone = "neutral" | "ask" | "escalate" | "proceed" | "brand";
export interface CaseStatusInfo {
  label: string;
  tone: StatusTone;
  group: "active" | "handover" | "closed";
}

type StatusInput = Pick<CaseListItem, "status" | "current_action" | "handover_status"> & {
  issue_titles?: string[];
  safety_state?: "NONE" | "UNCLEAR" | "HUMAN_CHECK" | "IMMEDIATE";
};

export function caseStatus(c: StatusInput): CaseStatusInfo {
  if (c.status === "CLOSED") return { label: "Abgeschlossen", tone: "neutral", group: "closed" };
  // a recognised acute danger outranks every other status, also in the list
  if (c.safety_state === "IMMEDIATE") return { label: "Akute Gefahr – Sicherheit klären", tone: "escalate", group: "active" };
  if (c.handover_status === "HANDOFF_COMPLETED") return { label: "Übergabe bestätigt", tone: "proceed", group: "handover" };
  if (c.handover_status === "HANDOFF_REQUESTED") return { label: "Übergabe angefragt", tone: "brand", group: "handover" };
  if (c.current_action === "ESCALATE") return { label: "Fachperson empfohlen", tone: "ask", group: "active" };
  // before the first analysis the backend reports ASK without any recognised problem
  if (c.current_action === "ASK" && c.issue_titles?.length === 0) return { label: "Noch nicht gestartet", tone: "neutral", group: "active" };
  if (c.current_action === "ASK") return { label: "Weitere Angaben nötig", tone: "ask", group: "active" };
  if (!c.current_action) return { label: "Noch nicht gestartet", tone: "neutral", group: "active" };
  return { label: "In Bearbeitung", tone: "neutral", group: "active" };
}

export type Phase = 1 | 2 | 3;
export const PHASES: { id: Phase; label: string }[] = [
  { id: 1, label: "Situation erfassen" },
  { id: 2, label: "Fragen klären" },
  { id: 3, label: "Nächste Schritte" },
];

/**
 * Orientation only, never a lock: phase 3 is reached as soon as the backend decision says ESCALATE/PROCEED,
 * even while questions are still open.
 */
export function currentPhase(detail: CaseDetail, messageCount: number): Phase {
  const d = detail.current_decision;
  if (messageCount === 0 || !d) return 1;
  if (d.action === "ESCALATE" || d.action === "PROCEED") return 3;
  const q = d.next_question;
  return q?.optional ? 3 : 2;
}
