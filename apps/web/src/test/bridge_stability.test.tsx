import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { BridgePanel, linkState } from "@/features/bridge/BridgePanel";
import type { MobileState, WorkerState } from "@/features/bridge/types";
import { errorResponse, mockApi, renderApp } from "./test-utils";

const question = {
  instance_id: "inst-0001",
  data_type: "boolean" as const,
  text: "Did you receive the notice?",
  why: "",
  options: [],
  optional: false,
};
const ok = (over: Partial<MobileState> = {}): MobileState => ({
  status: "QUESTION_ACTIVE",
  rev: 2,
  language: "en",
  rtl: false,
  question,
  notice: null,
  ...over,
});

function openPhone() {
  window.location.hash = "#t=tok-stability";
  renderApp("/bridge");
}

beforeEach(() => {
  sessionStorage.clear();
  window.location.hash = "";
});

describe("phone: reconnect behaviour", () => {
  it("one failed request is not «connection lost»; two are; recovery returns to the same question without a new scan", async () => {
    let n = 0;
    const { calls } = mockApi({
      "GET /bridge/state": () => {
        n += 1;
        if (n === 2) throw new TypeError("blip"); // a single hiccup
        if (n === 4 || n === 5) throw new TypeError("outage"); // a real outage (two in a row)
        return ok();
      },
    });
    openPhone();
    expect(await screen.findByTestId("bridge-question")).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 2800)); // the single failure happens and is retried
    expect(screen.queryByTestId("bridge-offline")).toBeNull();
    expect(screen.getByTestId("bridge-question")).toBeInTheDocument(); // the question stays while reconnecting
    expect(await screen.findByTestId("bridge-offline", {}, { timeout: 9000 })).toHaveTextContent("Reconnecting");
    expect(screen.getByTestId("bridge-question")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId("bridge-offline")).toBeNull(), { timeout: 9000 });
    expect(screen.queryByText(/ended/i)).toBeNull();
    // never a second QR/language step: no POST at all happened
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  }, 30000);

  it("server errors and rate limits are transient, not the end of the session", async () => {
    let n = 0;
    mockApi({
      "GET /bridge/state": () => {
        n += 1;
        if (n === 2) return errorResponse(500, "internal", "x");
        if (n === 3) return errorResponse(429, "too_many_requests", "x");
        return ok();
      },
    });
    openPhone();
    expect(await screen.findByTestId("bridge-question")).toBeInTheDocument();
    await waitFor(() => expect(n).toBeGreaterThanOrEqual(5), { timeout: 12000 });
    expect(screen.getByTestId("bridge-question")).toBeInTheDocument();
    expect(screen.queryByText(/interview has ended/)).toBeNull();
  }, 20000);

  it("a final 410 is clearly different: the interview has ended", async () => {
    let n = 0;
    mockApi({
      "GET /bridge/state": () => {
        n += 1;
        return n === 1 ? ok() : errorResponse(410, "bridge_ended", "x");
      },
    });
    openPhone();
    expect(await screen.findByTestId("bridge-question")).toBeInTheDocument();
    expect(await screen.findByText("This interview has ended. Please contact your social worker.", {}, { timeout: 6000 })).toBeInTheDocument();
    expect(screen.queryByTestId("bridge-offline")).toBeNull();
  }, 15000);

  it("waking the phone (network back / screen unlocked) refreshes at once instead of waiting for the backoff", async () => {
    let n = 0;
    let down = false;
    mockApi({
      "GET /bridge/state": () => {
        n += 1;
        if (down) throw new TypeError("offline");
        return ok();
      },
    });
    openPhone();
    await screen.findByTestId("bridge-question");
    down = true;
    await new Promise((r) => setTimeout(r, 2300)); // polls fail, backoff grows
    down = false;
    const before = n;
    await act(async () => {
      window.dispatchEvent(new Event("online"));
      await new Promise((r) => setTimeout(r, 400));
    });
    expect(n).toBeGreaterThan(before); // polled right away
    await waitFor(() => expect(screen.queryByTestId("bridge-offline")).toBeNull());
  }, 20000);

  it("never runs two polls at the same time", async () => {
    let inflight = 0;
    let max = 0;
    mockApi({
      "GET /bridge/state": async () => {
        inflight += 1;
        max = Math.max(max, inflight);
        await new Promise((r) => setTimeout(r, 350));
        inflight -= 1;
        return ok();
      },
    });
    openPhone();
    await screen.findByTestId("bridge-question");
    for (let i = 0; i < 4; i++) window.dispatchEvent(new Event("online")); // event storm
    await new Promise((r) => setTimeout(r, 2500));
    expect(max).toBe(1);
  }, 15000);

  it("an answer that could not be sent is retried with the SAME request id (no duplicates) until the server confirms", async () => {
    let posts = 0;
    let stored = false;
    const { calls } = mockApi({
      "GET /bridge/state": () => (stored ? ok({ status: "AWAITING_WORKER_REVIEW", question: null }) : ok()),
      "POST /bridge/answer": () => {
        posts += 1;
        if (posts <= 2) throw new TypeError("lost"); // the connection drops while sending
        stored = true;
        return ok({ status: "AWAITING_WORKER_REVIEW", question: null });
      },
    });
    openPhone();
    await userEvent.click(await screen.findByRole("button", { name: "Yes" }));
    expect(await screen.findByText("Answer sent", {}, { timeout: 12000 })).toBeInTheDocument();
    const ids = calls.filter((c) => c.path === "/bridge/answer").map((c) => (c.body as { request_id: string }).request_id);
    expect(ids).toHaveLength(3);
    expect(new Set(ids).size).toBe(1);
  }, 20000);

  it("an answer the server already stored (response lost) shows up through the poll, without sending twice", async () => {
    let stored = false;
    const { calls } = mockApi({
      "GET /bridge/state": () => (stored ? ok({ status: "AWAITING_WORKER_REVIEW", question: null }) : ok()),
      "POST /bridge/answer": () => {
        stored = true; // the server got it ...
        throw new TypeError("response lost"); // ... but the phone did not see the reply
      },
    });
    openPhone();
    await userEvent.click(await screen.findByRole("button", { name: "Yes" }));
    expect(await screen.findByText("Answer sent", {}, { timeout: 8000 })).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/bridge/answer").length).toBeLessThanOrEqual(2);
  }, 15000);

  it("a question that is still being translated is a normal wait, not an error", async () => {
    mockApi({ "GET /bridge/state": ok({ question: null, notice: "translation_pending" }) });
    openPhone();
    expect(await screen.findByText("Preparing the question …")).toBeInTheDocument();
    expect(screen.queryByTestId("bridge-offline")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

const worker = (over: Partial<WorkerState> = {}): WorkerState => ({
  active: true,
  session_id: "s1",
  status: "QUESTION_ACTIVE",
  rev: 4,
  language: "ar",
  language_name: "Arabisch",
  phone_connected: true,
  last_seen_seconds: 1,
  join_token: null,
  lan_ip: "192.168.1.20",
  lan_candidates: ["192.168.1.20"],
  public_base_url: null,
  expires_at: null,
  question: {
    instance_id: "i1",
    fact_id: "f1",
    text_de: "Wann haben Sie die Kündigung erhalten?",
    text_translated: null,
    translation_status: "PENDING",
    translation_error: null,
    translation_error_code: null,
    data_type: "string",
    options: [],
    options_de: [],
  },
  answer: null,
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

describe("desktop: clearly different states", () => {
  it("link state follows the phone's heartbeat: connected / interrupted (recovering) / away", () => {
    expect(linkState(worker({ last_seen_seconds: 3 })).state).toBe("connected");
    expect(linkState(worker({ last_seen_seconds: 30 })).state).toBe("interrupted");
    expect(linkState(worker({ last_seen_seconds: 30 })).label).toMatch(/Wiederherstellung läuft/);
    expect(linkState(worker({ last_seen_seconds: 400 })).state).toBe("away");
    expect(linkState(worker({ last_seen_seconds: 400 })).label).toMatch(/Sitzung bleibt gültig/);
  });

  it("a translation in progress is shown as such, still «verbunden»", async () => {
    mockApi({ "GET /cases/case-1/voice-bridge": worker() });
    renderPanel();
    expect(await screen.findByTestId("bridge-translating")).toHaveTextContent("wird übersetzt");
    expect(screen.getByTestId("bridge-link-state")).toHaveAttribute("data-state", "connected");
  });

  it("a failed translation names the reason and is never presented as a connection problem; retry is offered", async () => {
    const { calls } = mockApi({
      "GET /cases/case-1/voice-bridge": worker({
        question: {
          ...worker().question!,
          translation_status: "FAILED",
          translation_error: "Das Tageslimit für KI-Aufrufe ist erreicht (AI_DAILY_REQUEST_LIMIT). Es wurde nichts an Gemini gesendet.",
          translation_error_code: "limit",
        },
      }),
      "POST /cases/case-1/voice-bridge/retry-translation": worker(),
    });
    renderPanel();
    const box = await screen.findByTestId("bridge-translation-failed");
    expect(box).toHaveAttribute("data-code", "limit");
    expect(box).toHaveTextContent("Tageslimit");
    expect(box).toHaveTextContent("Verbindung zum Smartphone ist davon nicht betroffen");
    expect(screen.getByTestId("bridge-link-state")).toHaveAttribute("data-state", "connected");
    await userEvent.click(screen.getByRole("button", { name: "Übersetzung erneut versuchen" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/retry-translation"))).toBe(true));
  });

  it("an interrupted link and an ended session look different", async () => {
    mockApi({ "GET /cases/case-1/voice-bridge": worker({ last_seen_seconds: 40, question: null }) });
    renderPanel();
    expect(await screen.findByTestId("bridge-link-state")).toHaveAttribute("data-state", "interrupted");
  });

  it("when the session ends the panel says so instead of silently resetting", async () => {
    let active = true;
    mockApi({ "GET /cases/case-1/voice-bridge": () => (active ? worker({ question: null }) : { active: false }) });
    renderPanel();
    await screen.findByTestId("bridge-panel");
    active = false;
    expect(await screen.findByTestId("bridge-ended", {}, { timeout: 6000 })).toHaveTextContent("Sitzung beendet");
  }, 15000);
});
