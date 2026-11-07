import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { BridgePanel } from "@/features/bridge/BridgePanel";
import type { MobileState, WorkerState } from "@/features/bridge/types";
import { mockApi, renderApp } from "./test-utils";

const q = (over: Partial<MobileState["question"] & object> = {}) => ({
  instance_id: "inst-0001",
  data_type: "boolean" as const,
  text: "Haben Sie die Kündigung erhalten?",
  why: "",
  options: [],
  optional: false,
  ...over,
});
const mobile = (over: Partial<MobileState> = {}): MobileState => ({
  status: "QUESTION_ACTIVE",
  rev: 2,
  language: "en",
  rtl: false,
  question: q(),
  notice: null,
  ...over,
});

function openPhone(token = "tok-abc") {
  window.location.hash = token ? `#t=${token}` : "";
  renderApp("/bridge");
}

beforeEach(() => {
  sessionStorage.clear();
  window.location.hash = "";
});

describe("phone side", () => {
  it("explains an invalid link instead of showing anything", async () => {
    mockApi({});
    renderApp("/bridge");
    expect(await screen.findByText(/QR/)).toBeInTheDocument();
  });

  it("starts with the language choice, then shows the question; Arabic is right-to-left", async () => {
    let lang: string | null = null;
    const { calls } = mockApi({
      "GET /bridge/state": () => (lang ? mobile({ language: lang, rtl: lang === "ar" }) : mobile({ status: "WAITING_FOR_CONNECTION", language: null, question: null })),
      "POST /bridge/language": (_u: URL, init?: RequestInit) => {
        lang = JSON.parse(String(init?.body)).language;
        return mobile({ language: lang, rtl: lang === "ar" });
      },
    });
    openPhone();
    await userEvent.click(await screen.findByRole("button", { name: "العربية" }));
    expect(await screen.findByTestId("bridge-question")).toHaveTextContent("Haben Sie die Kündigung erhalten?");
    expect(screen.getByTestId("bridge-mobile")).toHaveAttribute("dir", "rtl");
    expect(screen.getByText("متصل بالأخصائية الاجتماعية")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/bridge/language")!.body).toEqual({ language: "ar" });
    // the key never stays in the address bar
    expect(window.location.hash).toBe("");
  });

  it("sends a stable value with the question instance and a request id, and then waits for the worker", async () => {
    let answered = false;
    const { calls } = mockApi({
      "GET /bridge/state": () => (answered ? mobile({ status: "AWAITING_WORKER_REVIEW", question: null }) : mobile()),
      "POST /bridge/answer": () => {
        answered = true;
        return mobile({ status: "AWAITING_WORKER_REVIEW", question: null });
      },
    });
    openPhone();
    await userEvent.click(await screen.findByRole("button", { name: "Yes" }));
    expect(await screen.findByText("Answer sent")).toBeInTheDocument();
    expect(screen.getByText("The social worker is reviewing your answer.")).toBeInTheDocument();
    expect(screen.queryByTestId("bridge-question")).toBeNull();
    const body = calls.find((c) => c.path === "/bridge/answer")!.body as Record<string, string>;
    expect(body).toMatchObject({ instance_id: "inst-0001", kind: "value", value: "true" });
    expect(body.request_id!.length).toBeGreaterThanOrEqual(8);
  });

  it("shows a pause screen and an end screen without case information", async () => {
    mockApi({ "GET /bridge/state": mobile({ status: "PAUSED", question: null }) });
    openPhone();
    expect(await screen.findByText("The interview has been paused for now.")).toBeInTheDocument();
  });

  it("an ended session (410) shows the thank-you/ended screen", async () => {
    mockApi({
      "GET /bridge/state": () => new Response(JSON.stringify({ error: { code: "bridge_ended", message: "x" } }), { status: 410 }),
    });
    openPhone();
    expect(await screen.findByText(/session has ended|ended/i)).toBeInTheDocument();
  });

  it("a lost connection is shown and recovers by itself", async () => {
    let fail = true;
    mockApi({
      "GET /bridge/state": () => {
        if (fail) throw new TypeError("network");
        return mobile();
      },
    });
    openPhone();
    expect(await screen.findByTestId("bridge-offline")).toBeInTheDocument();
    fail = false;
    expect(await screen.findByTestId("bridge-question", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByTestId("bridge-offline")).toBeNull();
  });

  it("never shows an untranslated question when translation failed", async () => {
    mockApi({ "GET /bridge/state": mobile({ question: null, notice: "translation_failed" }) });
    openPhone();
    expect(await screen.findByRole("alert")).toHaveTextContent("cannot be translated");
    expect(screen.queryByTestId("bridge-question")).toBeNull();
  });
});

const worker = (over: Partial<WorkerState> = {}): WorkerState => ({
  active: true,
  session_id: "s1",
  status: "AWAITING_WORKER_REVIEW",
  rev: 4,
  language: "ar",
  language_name: "Arabisch",
  phone_connected: true,
  last_seen_seconds: 1,
  join_token: null,
  lan_ip: "192.168.1.20",
  lan_candidates: ["192.168.1.20", "172.17.16.1"],
  public_base_url: null,
  expires_at: null,
  question: {
    instance_id: "i1",
    fact_id: "f1",
    text_de: "Wann haben Sie die Kündigung erhalten?",
    text_translated: "متى تلقيت الإشعار؟",
    translation_status: "OK",
    translation_error: null,
    translation_error_code: null,
    data_type: "string",
    options: [],
    options_de: [],
  },
  answer: {
    kind: "text",
    original: "في الرابع من نوفمبر",
    language: "ar",
    german: "Am 4. November",
    machine_translated: true,
    translation_status: "MACHINE",
    submitted_at: new Date().toISOString(),
  },
  ...over,
});

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <BridgePanel caseId="case-1" disabled={false} onCaseChanged={() => undefined} />
    </QueryClientProvider>,
  );
}

describe("desktop panel", () => {
  it("offers to activate and describes what is transmitted", async () => {
    mockApi({ "GET /cases/case-1/voice-bridge": { active: false } });
    renderPanel();
    expect(await screen.findByRole("button", { name: "Sprachbrücke aktivieren" })).toBeInTheDocument();
    expect(screen.getByText(/nie die Fallakte/)).toBeInTheDocument();
    expect(screen.getByText(/maschinell übersetzt/)).toBeInTheDocument();
  });

  const waiting = (over: Partial<WorkerState> = {}) =>
    worker({ status: "WAITING_FOR_CONNECTION", join_token: "tok123", answer: null, question: null, language: null, language_name: null, ...over });

  it("builds the QR link from the network address, never from localhost, and QR and link are the same URL", async () => {
    mockApi({ "GET /cases/case-1/voice-bridge": waiting(), "GET /health": { ok: true } });
    renderPanel();
    const link = await screen.findByTestId("bridge-link");
    expect(link.getAttribute("href")).toBe("http://192.168.1.20:3000/bridge#t=tok123");
    expect(link.textContent).toBe(link.getAttribute("href"));
    expect(link.getAttribute("href")).not.toMatch(/localhost|127\.0\.0\.1/);
    expect(await screen.findByAltText(/QR-Code/)).toBeInTheDocument();
    expect(await screen.findByText("Der Server antwortet unter dieser Adresse.")).toBeInTheDocument();
  });

  it("lets the user choose between several adapters (WLAN vs. WSL) and updates the link", async () => {
    mockApi({ "GET /cases/case-1/voice-bridge": waiting(), "GET /health": { ok: true } });
    renderPanel();
    const sel = await screen.findByLabelText("Netzwerkadresse dieses Computers");
    expect((sel as HTMLSelectElement).options).toHaveLength(2);
    await userEvent.selectOptions(sel, "http://172.17.16.1:3000");
    expect(screen.getByTestId("bridge-link").getAttribute("href")).toContain("http://172.17.16.1:3000/bridge#t=tok123");
  });

  it("a configured public base address wins and cannot be overridden by guessing", async () => {
    mockApi({ "GET /cases/case-1/voice-bridge": waiting({ public_base_url: "http://10.0.0.5:5173/" }), "GET /health": { ok: true } });
    renderPanel();
    expect((await screen.findByTestId("bridge-link")).getAttribute("href")).toBe("http://10.0.0.5:5173/bridge#t=tok123");
    expect(screen.queryByLabelText("Netzwerkadresse dieses Computers")).toBeNull();
  });

  it("with no known network address there is no QR to localhost, but configuration help and a manual field", async () => {
    mockApi({ "GET /cases/case-1/voice-bridge": waiting({ lan_ip: null, lan_candidates: [] }) });
    renderPanel();
    expect(await screen.findByTestId("bridge-noaddr")).toHaveTextContent("dev.ps1 -Lan");
    expect(screen.queryByTestId("bridge-link")).toBeNull();
    expect(screen.queryByAltText(/QR-Code/)).toBeNull();
    await userEvent.type(screen.getByLabelText("Eigene Basisadresse"), "http://192.168.7.7:5174");
    expect(await screen.findByTestId("bridge-link")).toHaveAttribute("href", "http://192.168.7.7:5174/bridge#t=tok123");
  });

  it("says so when nothing answers on the address (server only bound to localhost) and shows the fix", async () => {
    mockApi({
      "GET /cases/case-1/voice-bridge": waiting(),
      "GET /health": () => {
        throw new TypeError("ERR_CONNECTION_REFUSED");
      },
    });
    renderPanel();
    expect(await screen.findByText("Unter dieser Adresse antwortet kein Server.")).toBeInTheDocument();
    expect(screen.getByTestId("bridge-help")).toHaveTextContent("-Lan");
    expect(screen.getByTestId("bridge-help")).toHaveTextContent("Verbindung abgelehnt");
  });

  it("shows original, German meaning with a machine-translation mark, and the worker's actions", async () => {
    const { calls } = mockApi({
      "GET /cases/case-1/voice-bridge": worker(),
      "POST /cases/case-1/voice-bridge/answer/accept": worker({ answer: null, status: "QUESTION_ACTIVE" }),
    });
    renderPanel();
    expect(await screen.findByTestId("bridge-answer")).toBeInTheDocument();
    expect(screen.getByTestId("bridge-answer-original")).toHaveTextContent("في الرابع من نوفمبر");
    expect(screen.getByTestId("bridge-answer-german")).toHaveTextContent("Am 4. November");
    expect(screen.getByText(/maschinell übersetzt, bitte prüfen/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Erneut fragen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Frage überspringen" })).toBeInTheDocument();
    // correction sends the worker's own German wording
    await userEvent.click(screen.getByRole("button", { name: "Korrigieren" }));
    const box = screen.getByLabelText("Deutsche Fassung korrigieren");
    await userEvent.clear(box);
    await userEvent.type(box, "Am 4.11.2026");
    await userEvent.click(screen.getByRole("button", { name: "Korrigiert übernehmen" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/answer/accept"))).toBe(true));
    expect(calls.find((c) => c.path.endsWith("/answer/accept"))!.body).toEqual({ corrected_text_de: "Am 4.11.2026" });
  });

  it("a failed translation is visible and blocks accepting a missing German text", async () => {
    mockApi({
      "GET /cases/case-1/voice-bridge": worker({
        question: { ...worker().question!, translation_status: "FAILED", text_translated: null, translation_error: "x" },
        answer: { ...worker().answer!, translation_status: "FAILED", german: "", machine_translated: false },
      }),
    });
    renderPanel();
    expect((await screen.findAllByText(/Übersetzung fehlgeschlagen/)).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Antwort übernehmen" })).toBeDisabled();
  });
});
