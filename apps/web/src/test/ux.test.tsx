import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { DecisionResult } from "@/types";
import { askDecision, briefing, escalateDecision, knownFact, makeCase, missingFact } from "./fixtures";
import { errorResponse, kbStatusRoute, mockApi, renderApp, statusRoute } from "./test-utils";

const msg = {
  id: "m1", role: "SOCIAL_WORKER", kind: "DESCRIPTION", content: "Der Vermieter hat gekündigt.", answers_fact_id: null,
  analysis_status: "DONE", analysis_error: null, created_at: new Date().toISOString(),
};
const view = (id: string) => ({ id, version: 1, case_version: 3, created_at: new Date().toISOString(), briefing });
const posted = { message: {}, analysis: { status: "OK", pending_message_ids: [], warnings: [] }, case: makeCase() };

function routes(decision: DecisionResult, over: Record<string, unknown> = {}, messages: unknown[] = [msg]) {
  return {
    "GET /system/status": statusRoute,
    "GET /knowledge-base/status": kbStatusRoute,
    "GET /cases/case-1": makeCase({ current_decision: decision }),
    "GET /cases/case-1/messages": messages,
    "GET /cases/case-1/facts": [knownFact, missingFact],
    "GET /cases/case-1/decisions": [],
    "GET /cases/case-1/briefings": [],
    ...over,
  };
}

const optionalQ = { ...escalateDecision.next_question!, fact_id: "rent_amount", question_de: "Wie hoch ist der Mietzins?", data_type: "integer", optional: true };
const optionalFact = { fact_id: "rent_amount", issue_ids: [], label_de: "Mietzins", status: "MISSING", priority: "low", question_de: "Wie hoch ist der Mietzins?", why_needed_de: "", deferred: false, data_type: "integer", enum_values: [], enum_labels_de: {}, handover_priority: "normal" };
// escalation, no important facts left open, one optional question available
const escalateWithOptional = { ...escalateDecision, missing_facts: [], optional_open_facts: [optionalFact], intake: { important_open: 0, optional_open: 1, deferred: 0, unknown: 0, known: 3, complete: true }, next_question: optionalQ, max_urgency: "HIGH" } as unknown as DecisionResult;

describe("three phases", () => {
  it("phase 1: only the plain question, no summary, no stepper lock", async () => {
    mockApi(routes(askDecision, {}, []));
    renderApp("/cases/case-1");
    expect(await screen.findByLabelText("Was ist passiert?")).toBeInTheDocument();
    expect(screen.getByText(/oder importieren Sie eine bereits verfasste Fallbeschreibung als PDF/)).toBeInTheDocument();
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Situation erfassen");
    expect(screen.queryByText("Alle Fallinformationen")).toBeNull();
  });

  it("phase 2: one question, no codes, no confidence percentages, no rule ids", async () => {
    mockApi(routes(askDecision));
    renderApp("/cases/case-1");
    await screen.findByText("Wurde die Kündigung schriftlich ausgesprochen?");
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Fragen klären");
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/\d+ ?%/);
    expect(body).not.toContain("MISSING_REQUIRED_FACTS");
    expect(screen.getByRole("button", { name: /Weiss nicht/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Später beantworten/ })).toBeInTheDocument();
  });

  it("phase 3 is reached on ESCALATE even though questions are still open", async () => {
    mockApi(routes(escalateWithOptional));
    renderApp("/cases/case-1");
    expect(await screen.findByText("Dringende Prüfung durch eine Fachperson empfohlen")).toBeInTheDocument();
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Nächste Schritte");
    expect(screen.getAllByText("Es läuft eine Frist. Die Beurteilung muss durch eine Fachperson erfolgen.").length).toBeGreaterThan(0);
    // urgent situation: explicit, visible human action that the report does not replace
    expect(screen.getByRole("alert")).toHaveTextContent(/umgehend Kontakt mit einer geeigneten Fachperson/);
    expect(screen.getByRole("alert")).toHaveTextContent(/Fallbericht ersetzt diese Kontaktaufnahme nicht/);
    // three clearly separated areas
    expect(screen.getByRole("region", { name: "Einschätzung" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Fallaufnahme vervollständigen" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Ergänzende Angaben (optional)" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Fallbericht" })).toBeInTheDocument();
    // optional questions never block or auto-start; the report stays one click away
    expect(screen.queryByText("Wie hoch ist der Mietzins?")).toBeNull();
    expect(screen.getByText("1 ergänzende Frage verfügbar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Fallbericht erstellen/ })).toBeEnabled();
  });
});

describe("intake continues after an escalation", () => {
  it("shows the important open facts one at a time, with count, without blocking the report", async () => {
    const q = { fact_id: "official_form_used", issue_ids: [], label_de: "Formular", status: "MISSING", priority: "high", question_de: "Wurde das amtliche Formular verwendet?", why_needed_de: "Formmangel", deferred: false, data_type: "boolean", enum_values: [], enum_labels_de: {}, handover_priority: "high" };
    const d = { ...escalateDecision, max_urgency: "HIGH", missing_facts: [q, { ...q, fact_id: "x2", question_de: "Zweite Frage?" }], optional_open_facts: [], intake: { important_open: 2, optional_open: 0, deferred: 0, unknown: 0, known: 1, complete: false } } as unknown as DecisionResult;
    mockApi(routes(d));
    renderApp("/cases/case-1");
    const region = await screen.findByRole("region", { name: "Fallaufnahme vervollständigen" });
    expect(within(region).getByText("Noch 2 wichtige Angaben offen.")).toBeInTheDocument();
    expect(within(region).getByText("Wurde das amtliche Formular verwendet?")).toBeInTheDocument();
    expect(within(region).queryByText("Zweite Frage?")).toBeNull(); // exactly one question
    expect(within(region).getByText(/Kontaktaufnahme mit der Fachperson muss nicht warten/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Fallbericht erstellen/ })).toBeEnabled(); // report any time
  });
});

describe("handover and briefing access", () => {
  it("offers «Fallbericht ansehen» once a briefing exists (briefing itself untouched)", async () => {
    mockApi(routes(escalateDecision, { "GET /cases/case-1": makeCase({ current_decision: escalateDecision, latest_briefing_id: "b1" }), "GET /cases/case-1/briefings": [{ id: "b1", version: 1, created_at: new Date().toISOString() }] }));
    renderApp("/cases/case-1");
    const link = await screen.findByRole("link", { name: /Fallbericht ansehen/ });
    expect(link).toHaveAttribute("href", "/cases/case-1/briefing");
    expect(screen.getByRole("link", { name: /PDF herunterladen/ })).toHaveAttribute("href", "/api/cases/case-1/briefings/b1/pdf");
  });

  it("shows «Fallbericht aktualisieren» when the case changed since the last report (old versions stay)", async () => {
    const { calls } = mockApi(
      routes(escalateDecision, {
        "GET /cases/case-1": makeCase({ current_decision: escalateDecision, briefing_stale: true, latest_briefing_id: "b1" }),
        "GET /cases/case-1/briefings": [{ id: "b1", version: 1, case_version: 2, created_at: new Date().toISOString() }],
        "POST /cases/case-1/briefings": { id: "b2" },
        "GET /cases/case-1/briefings/b2": view("b2"),
      }),
    );
    renderApp("/cases/case-1");
    expect(await screen.findByText(/Seit dem letzten Fallbericht wurden neue Angaben erfasst/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Letzten Fallbericht ansehen" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fallbericht aktualisieren" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/cases/case-1/briefings")).toBe(true));
  });

  it("report creation and handover are separate: creating a report never marks a handover", async () => {
    const { calls } = mockApi(
      routes(escalateDecision, { "POST /cases/case-1/briefings": { id: "b1" }, "GET /cases/case-1/briefings/b1": view("b1") }),
    );
    renderApp("/cases/case-1");
    expect(await screen.findByText(/Der Fallbericht ist keine Kontaktaufnahme mit einer Fachperson/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fallbericht erstellen" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/cases/case-1/briefings" && c.method === "POST")).toBe(true));
    expect(calls.some((c) => c.path.includes("handover"))).toBe(false);
  });

  it("shows a clear error and keeps the button available when the report fails", async () => {
    mockApi(routes(escalateDecision, { "POST /cases/case-1/briefings": () => errorResponse(500, "boom", "Interner Fehler") }));
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: "Fallbericht erstellen" }));
    expect(await screen.findByText(/Der Fallbericht konnte nicht erstellt werden: Interner Fehler/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fallbericht erstellen" })).toBeEnabled();
  });

  it("«Fallbericht erstellen» creates the briefing through the existing API", async () => {
    const { calls } = mockApi(
      routes(escalateDecision, {
        "POST /cases/case-1/briefings": { id: "b1" },
        "GET /cases/case-1/briefings/b1": view("b1"),
      }),
    );
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: /Fallbericht erstellen/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/cases/case-1/briefings")).toBe(true));
  });

  it("never claims that anybody was contacted: recommended, requested, confirmed are distinct", async () => {
    mockApi(
      routes(escalateDecision, {
        "GET /cases/case-1": makeCase({
          current_decision: escalateDecision,
          handover: { status: "HANDOFF_REQUESTED", professional_types: [], reasons: [], requested_at: null, completed_at: null, completion_note: null },
        }),
      }),
    );
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByText("Übergabestatus verwalten"));
    expect(await screen.findByText(/Übergabe angefragt\. Bestätigen Sie sie/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Übergabe bestätigen" })).toBeInTheDocument();
  });

  it("shows only the two most important reasons by default; all details are one click away", async () => {
    const many = {
      ...escalateDecision,
      triggered_rules: ["A", "B", "C"].map((x, i) => ({
        ...escalateDecision.triggered_rules[0]!, rule_id: `R_${x}`, reason_code: `CODE_${x}`, reason_de: `Grund ${x}`, urgency: i === 2 ? "HIGH" : "LOW",
      })),
    } as unknown as DecisionResult;
    mockApi(routes(many));
    renderApp("/cases/case-1");
    const details = await screen.findByTestId("decision-details");
    // highest urgency first in the main view: C (HIGH), then A
    const main = screen.getByRole("region", { name: "Einschätzung" }).querySelector("ul") as HTMLElement;
    expect(within(main).getByText("Grund C")).toBeInTheDocument();
    expect(within(main).getByText("Grund A")).toBeInTheDocument();
    expect(within(main).queryByText("Grund B")).toBeNull();
    expect(within(details).getByText("Grund B")).toBeInTheDocument();
    expect(within(details).getByText("CODE_B")).toBeInTheDocument();
  });
});

describe("optional questions", () => {
  it("are opt-in, asked one at a time, skippable and endable", async () => {
    const { calls } = mockApi(routes(escalateWithOptional, { "POST /cases/case-1/facts/rent_amount/defer": [missingFact] }));
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: "Ergänzende Fragen beantworten" }));
    expect(await screen.findByText("Wie hoch ist der Mietzins?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Überspringen" }));
    await waitFor(() => expect(calls.find((c) => c.path.endsWith("/defer"))?.body).toEqual({ reason: "Bei der Fallaufnahme übersprungen" }));
    await userEvent.click(screen.getByRole("button", { name: "Ergänzung beenden" }));
    expect(screen.queryByText("Wie hoch ist der Mietzins?")).toBeNull();
    expect(screen.getByRole("button", { name: /Fallbericht erstellen/ })).toBeEnabled();
  });

  it("do not reappear once skipped (deferred questions are not offered again)", async () => {
    mockApi(routes({ ...escalateWithOptional, optional_open_facts: [{ ...optionalFact, deferred: true }] } as unknown as DecisionResult));
    renderApp("/cases/case-1");
    await screen.findByText("Dringende Prüfung durch eine Fachperson empfohlen");
    expect(screen.queryByRole("button", { name: "Ergänzende Fragen beantworten" })).toBeNull();
  });
});

describe("free text stays available and quiet", () => {
  it("the guided question is primary; extra information opens on demand and posts a NOTE through the normal pipeline", async () => {
    const { calls } = mockApi({ ...routes(askDecision), "POST /cases/case-1/messages": posted });
    renderApp("/cases/case-1");
    await screen.findByText("Wurde die Kündigung schriftlich ausgesprochen?");
    expect(screen.queryByLabelText("Weitere Informationen aus dem Gespräch")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Weitere Informationen aus dem Gespräch ergänzen/ }));
    await userEvent.type(screen.getByLabelText("Weitere Informationen aus dem Gespräch"), "Sie hat einen Gerichtsbrief erhalten.");
    await userEvent.click(screen.getByRole("button", { name: /^Erfassen$/ }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toEqual({ content: "Sie hat einen Gerichtsbrief erhalten.", kind: "NOTE" }));
  });
});

describe("pure UI interaction never triggers analysis (no extra AI cost)", () => {
  it("opening facts, the history and the legal hints only issues GET requests", async () => {
    const { calls } = mockApi(routes(askDecision));
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: /Alle Fallinformationen/ }));
    await screen.findByRole("region", { name: "Fallverständnis" });
    await userEvent.click(screen.getByRole("button", { name: "Schliessen" }));
    await userEvent.click(screen.getByText("Gesprächsverlauf anzeigen"));
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
  });
});

describe("developer area is not part of the normal navigation", () => {
  it("is reachable by URL and lists the technical tools", async () => {
    mockApi({ "GET /system/status": statusRoute, "GET /knowledge-base/status": kbStatusRoute });
    renderApp("/dev");
    expect(await screen.findByRole("heading", { name: "Entwicklerbereich" })).toBeInTheDocument();
    for (const name of ["Knowledge Base", "Evaluation", "Geführte Demo"]) expect(screen.getByText(name)).toBeInTheDocument();
  });
});
