import type { WorkerState } from "@/features/bridge/types";
import type {
  AIUsageReport,
  BriefingListItem,
  BriefingOverviewItem,
  BriefingView,
  CaseDetail,
  CaseListItem,
  DashboardData,
  DecisionResult,
  DecisionView,
  EvaluationSummary,
  FactView,
  KbIssue,
  KbStatus,
  MessageResult,
  MessageView,
  ScenarioListItem,
  SystemStatus,
} from "@/types";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: { field: string; message: string }[];

  constructor(status: number, code: string, message: string, details?: ApiError["details"]) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "network_error", "Der Server ist nicht erreichbar. Läuft das Backend?");
  }
  if (!res.ok) {
    let code = "http_error";
    let message = `Anfrage fehlgeschlagen (${res.status}).`;
    let details: ApiError["details"];
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code;
        message = body.error.message;
        details = body.error.details ?? undefined;
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message, details);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export interface CaseFilters {
  q?: string;
  status?: string;
  action?: string;
  sort?: string;
}

export const api = {
  systemStatus: () => request<SystemStatus>("/system/status"),
  dashboard: () => request<DashboardData>("/dashboard"),

  listCases: (f: CaseFilters = {}) => {
    const p = new URLSearchParams();
    Object.entries(f).forEach(([k, v]) => v && p.set(k, v));
    const qs = p.toString();
    return request<CaseListItem[]>(`/cases${qs ? `?${qs}` : ""}`);
  },
  aiUsage: () => request<AIUsageReport>("/ai/usage"),
  createCase: (title = "") => request<CaseDetail>("/cases", json("POST", { title })),
  getCase: (id: string) => request<CaseDetail>(`/cases/${id}`),
  patchCase: (id: string, body: { title?: string; status?: "OPEN" | "CLOSED" }) =>
    request<CaseDetail>(`/cases/${id}`, json("PATCH", body)),

  listMessages: (id: string) => request<MessageView[]>(`/cases/${id}/messages`),
  postMessage: (
    id: string,
    body: {
      content: string;
      answers_fact_id?: string | null;
      kind?: "DESCRIPTION" | "NOTE";
      unknown?: boolean;
    },
  ) =>
    request<MessageResult>(`/cases/${id}/messages`, json("POST", body)),
  /** Extract the text of a written case description from a PDF (nothing is stored server-side). */
  importPdfText: (file: File) =>
    request<{ text: string; pages: number; truncated: boolean }>("/intake/pdf-text", {
      method: "POST",
      headers: { "Content-Type": "application/pdf" },
      body: file,
    }),
  bridge: {
    get: (id: string) => request<WorkerState>(`/cases/${id}/voice-bridge`),
    start: (id: string) => request<WorkerState>(`/cases/${id}/voice-bridge`, json("POST")),
    pause: (id: string) => request<WorkerState>(`/cases/${id}/voice-bridge/pause`, json("POST")),
    resume: (id: string) => request<WorkerState>(`/cases/${id}/voice-bridge/resume`, json("POST")),
    end: (id: string) => request<WorkerState>(`/cases/${id}/voice-bridge/end`, json("POST")),
    accept: (id: string, body: { corrected_value?: string; corrected_text_de?: string }) =>
      request<WorkerState>(`/cases/${id}/voice-bridge/answer/accept`, json("POST", body)),
    reask: (id: string) => request<WorkerState>(`/cases/${id}/voice-bridge/answer/reask`, json("POST")),
    skip: (id: string) => request<WorkerState>(`/cases/${id}/voice-bridge/skip`, json("POST")),
    retryTranslation: (id: string) => request<WorkerState>(`/cases/${id}/voice-bridge/retry-translation`, json("POST")),
  },
  analyze: (id: string) => request<CaseDetail>(`/cases/${id}/analyze`, json("POST")),

  listFacts: (id: string) => request<FactView[]>(`/cases/${id}/facts`),
  patchFact: (
    id: string,
    factId: string,
    body: {
      value?: string | boolean | number;
      status?: "MISSING" | "NOT_APPLICABLE" | "UNKNOWN";
      confirmed?: boolean;
      documented?: boolean;
      note?: string;
    },
  ) => request<FactView[]>(`/cases/${id}/facts/${factId}`, json("PATCH", body)),
  acknowledgeSafety: (id: string, eventId: string, note: string) =>
    request<DecisionResult>(`/cases/${id}/safety-events/${eventId}/acknowledge`, json("POST", { note })),
  deferFact: (id: string, factId: string, reason: string) =>
    request<FactView[]>(`/cases/${id}/facts/${factId}/defer`, json("POST", { reason })),
  undeferFact: (id: string, factId: string) =>
    request<FactView[]>(`/cases/${id}/facts/${factId}/undefer`, json("POST")),

  decisions: (id: string) => request<DecisionView[]>(`/cases/${id}/decisions`),

  requestHandover: (id: string) => request<CaseDetail>(`/cases/${id}/handover/request`, json("POST")),
  completeHandover: (id: string, note: string) =>
    request<CaseDetail>(`/cases/${id}/handover/complete`, json("POST", { note })),

  listBriefings: (id: string) => request<BriefingListItem[]>(`/cases/${id}/briefings`),
  createBriefing: (id: string) => request<BriefingView>(`/cases/${id}/briefings`, json("POST")),
  getBriefing: (id: string, briefingId: string) =>
    request<BriefingView>(`/cases/${id}/briefings/${briefingId}`),
  briefingOverview: () => request<BriefingOverviewItem[]>("/briefings"),

  kbStatus: () => request<KbStatus>("/knowledge-base/status"),
  kbIssues: () => request<KbIssue[]>("/knowledge-base/issues"),
  kbReload: () => request<KbStatus>("/knowledge-base/reload", json("POST")),

  evaluationScenarios: () => request<ScenarioListItem[]>("/evaluation/scenarios"),
  runEvaluation: () => request<EvaluationSummary>("/evaluation/run", json("POST")),
};
