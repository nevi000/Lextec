/** Wire types of the Sprachbrücke endpoints (hand-written; mirror app/schemas/bridge.py). */
export type BridgeStatus =
  | "WAITING_FOR_CONNECTION"
  | "WAITING_FOR_QUESTION"
  | "QUESTION_ACTIVE"
  | "AWAITING_WORKER_REVIEW"
  | "PAUSED"
  | "COMPLETED"
  | "EXPIRED";

export interface BridgeOption {
  value: string;
  label: string;
}

export interface MobileQuestion {
  instance_id: string;
  data_type: "string" | "boolean" | "date" | "integer" | "enum";
  text: string;
  why: string;
  options: BridgeOption[];
  optional: boolean;
}

export interface MobileState {
  status: BridgeStatus;
  rev: number;
  language: string | null;
  rtl: boolean;
  question: MobileQuestion | null;
  notice: "translation_failed" | "translation_pending" | null;
}

export interface PendingAnswer {
  kind: "value" | "unknown" | "text";
  original: string;
  language: string;
  german: string;
  machine_translated: boolean;
  translation_status: "STRUCTURED" | "ORIGINAL_GERMAN" | "MACHINE" | "FAILED";
  submitted_at: string;
}

export interface WorkerQuestion {
  instance_id: string;
  fact_id: string;
  text_de: string;
  text_translated: string | null;
  translation_status: "NONE" | "PENDING" | "OK" | "FAILED";
  translation_error_code: string | null;
  translation_error: string | null;
  data_type: string;
  options: BridgeOption[];
  options_de: BridgeOption[];
}

export interface WorkerState {
  active: boolean;
  session_id: string | null;
  status: BridgeStatus | null;
  rev: number;
  language: string | null;
  language_name: string | null;
  phone_connected: boolean;
  last_seen_seconds: number | null;
  join_token: string | null;
  lan_ip: string | null;
  lan_candidates: string[];
  public_base_url: string | null;
  expires_at: string | null;
  question: WorkerQuestion | null;
  answer: PendingAnswer | null;
}
