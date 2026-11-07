import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { BriefingDocument } from "@/features/briefings/BriefingDocument";
import { displayValue, parseServerDate } from "@/lib/utils";
import { render } from "@testing-library/react";
import {
  askDecision,
  briefing,
  escalateDecision,
  knownFact,
  listItem,
  makeCase,
  missingFact,
} from "./fixtures";
import { errorResponse, kbStatusRoute, mockApi, renderApp, statusRoute } from "./test-utils";
import type { BriefingView } from "@/types";

const baseRoutes = {
  "GET /system/status": statusRoute,
  "GET /knowledge-base/status": kbStatusRoute,
};

describe("utils", () => {
  it("formats fact values for display", () => {
    expect(displayValue(true)).toBe("Ja");
    expect(displayValue(false)).toBe("Nein");
    expect(displayValue("2026-01-15")).toBe("15.01.2026");
    expect(displayValue(null)).toBe("–");
  });
  it("treats naive server timestamps as UTC", () => {
    expect(parseServerDate("2026-01-01T10:00:00").toISOString()).toBe("2026-01-01T10:00:00.000Z");
  });
});

describe("start page: Meine Fälle", () => {
  it("shows the plain case list with plain-language status and no dashboard metrics", async () => {
    mockApi({ ...baseRoutes, "GET /cases": [listItem] });
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Meine Fälle" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Arbeitskündigung/ })).toBeInTheDocument();
    expect(screen.getByText("Weitere Angaben nötig")).toBeInTheDocument();
    expect(screen.queryByTestId("metrics")).toBeNull();
    expect(screen.queryByText("FALL-0001")).toBeNull();
  });

  it("navigation only offers Meine Fälle and Neuen Fall erfassen", async () => {
    mockApi({ ...baseRoutes, "GET /cases": [] });
    renderApp("/");
    const nav = (await screen.findAllByRole("navigation", { name: "Hauptnavigation" }))[0]!;
    expect(within(nav).getAllByRole("link")).toHaveLength(1);
    for (const hidden of ["Demo Mietkündigung", "Evaluation", "Knowledge Base", "Einstellungen", "Expert Briefings"]) {
      expect(screen.queryByText(hidden)).toBeNull();
    }
  });

  it("shows an empty state without cases", async () => {
    mockApi({ ...baseRoutes, "GET /cases": [] });
    renderApp("/");
    expect(await screen.findByText("Noch keine Fälle erfasst")).toBeInTheDocument();
  });

  it("shows an error state", async () => {
    mockApi({ ...baseRoutes, "GET /cases": () => errorResponse(500, "boom", "Interner Fehler") });
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Interner Fehler");
  });

  it("filters by working state", async () => {
    mockApi({
      ...baseRoutes,
      "GET /cases": [
        listItem,
        { ...listItem, id: "c2", title: "Zweiter Fall", current_action: "ESCALATE", handover_status: "HANDOFF_REQUESTED" },
        { ...listItem, id: "c3", title: "Dritter Fall", status: "CLOSED" },
      ],
    });
    renderApp("/");
    await screen.findByText("Zweiter Fall");
    expect(screen.getByText("Übergabe angefragt")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Übergabe" }));
    expect(screen.queryByText("Dritter Fall")).toBeNull();
    expect(screen.getByText("Zweiter Fall")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Abgeschlossen" }));
    expect(screen.getByText("Dritter Fall")).toBeInTheDocument();
    expect(screen.queryByText("Zweiter Fall")).toBeNull();
  });
});

describe("case list", () => {
  it("searches via the API and opens a case", async () => {
    const { calls } = mockApi({ ...baseRoutes, "GET /cases": [listItem] });
    renderApp("/");
    expect(await screen.findByRole("link", { name: /Arbeitskündigung/ })).toHaveAttribute("href", "/cases/case-1");
    await userEvent.type(screen.getByLabelText("Fälle durchsuchen"), "Kündigung");
    await waitFor(() => expect(calls.filter((c) => c.path === "/cases").length).toBeGreaterThan(1));
  });

  it("creates a new case and opens phase 1 with the plain question", async () => {
    const created = makeCase({ current_decision: { ...askDecision, next_question: { ...askDecision.next_question!, fact_id: null } } as never });
    const { calls } = mockApi({
      ...baseRoutes,
      "GET /cases": [],
      "POST /cases": created,
      "GET /cases/case-1": created,
      "GET /cases/case-1/messages": [],
      "GET /cases/case-1/facts": [],
      "GET /cases/case-1/decisions": [],
      "GET /cases/case-1/briefings": [],
    });
    renderApp("/");
    expect(await screen.findByText("Noch keine Fälle erfasst")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: /Neuen Fall erfassen/ })[0]!);
    expect(await screen.findByLabelText("Was ist passiert?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Situation analysieren/ })).toBeDisabled();
    expect(calls.some((c) => c.method === "POST" && c.path === "/cases")).toBe(true);
  });
});

describe("consultation workspace", () => {
  const workspaceRoutes = (over: Record<string, unknown> = {}) => ({
    ...baseRoutes,
    "GET /cases/case-1": makeCase(),
    "GET /cases/case-1/messages": [
      { id: "m1", role: "SOCIAL_WORKER", kind: "DESCRIPTION", content: "Mein Arbeitgeber hat mir gekündigt.", answers_fact_id: null, analysis_status: "DONE", analysis_error: null, created_at: new Date().toISOString() },
    ],
    "GET /cases/case-1/facts": [knownFact, missingFact],
    "GET /cases/case-1/decisions": [],
    "GET /cases/case-1/briefings": [],
    ...over,
  });

  it("shows the next question, reason, and posts a selected yes/no answer with one primary button", async () => {
    const { calls } = mockApi({
      ...workspaceRoutes(),
      "POST /cases/case-1/messages": { message: {}, analysis: { status: "OK", pending_message_ids: [], warnings: [] }, case: makeCase() },
    });
    renderApp("/cases/case-1");
    expect(await screen.findByText("Wurde die Kündigung schriftlich ausgesprochen?")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Warum ist das wichtig?"));
    expect(screen.getByText("Die Form der Kündigung ist relevant.")).toBeVisible();
    const save = screen.getByRole("button", { name: "Antwort speichern und weiter" });
    expect(save).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: "Ja" }));
    await userEvent.click(save);
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/cases/case-1/messages")).toBeDefined());
    const post = calls.find((c) => c.method === "POST" && c.path === "/cases/case-1/messages")!;
    expect(post.body).toEqual({ content: "Ja", answers_fact_id: "employer_termination_in_writing" });
  });

  it("distinguishes AI-extracted facts and shows their evidence in the fact dialog", async () => {
    mockApi(workspaceRoutes());
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: /Alle Fallinformationen/ }));
    const panel = await screen.findByRole("region", { name: "Fallverständnis" });
    expect(within(panel).getByText("Aus Schilderung (KI)")).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: /Kündigung durch Arbeitgeber erhalten/ }));
    const dialog = (await screen.findAllByRole("dialog")).at(-1)!;
    expect(within(dialog).getByText("Arbeitgeber hat mir gekündigt", { selector: "q" })).toBeInTheDocument();
  });

  it("validates and submits a fact correction", async () => {
    const { calls } = mockApi({ ...workspaceRoutes(), "PATCH /cases/case-1/facts/employer_termination_received": [knownFact] });
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: /Alle Fallinformationen/ }));
    const panel = await screen.findByRole("region", { name: "Fallverständnis" });
    await userEvent.click(within(panel).getByRole("button", { name: /Kündigung durch Arbeitgeber erhalten/ }));
    const dialog = (await screen.findAllByRole("dialog")).at(-1)!;
    const select = within(dialog).getByLabelText("Wert korrigieren oder ergänzen");
    await userEvent.selectOptions(select, "");
    await userEvent.click(within(dialog).getByRole("button", { name: "Speichern" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Bitte einen Wert angeben.");
    await userEvent.selectOptions(select, "nein");
    await userEvent.click(within(dialog).getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")).toBeDefined());
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ value: "nein" });
  });

  it("requires a reason to defer a question", async () => {
    const { calls } = mockApi({ ...workspaceRoutes(), "POST /cases/case-1/facts/employer_termination_in_writing/defer": [missingFact] });
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: /Später beantworten/ }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Zurückstellen" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("mind. 3 Zeichen");
    expect(calls.some((c) => c.path.endsWith("/defer"))).toBe(false);
    await userEvent.type(within(dialog).getByLabelText("Grund für die Zurückstellung"), "Unterlagen fehlen");
    await userEvent.click(within(dialog).getByRole("button", { name: "Zurückstellen" }));
    await waitFor(() => expect(calls.find((c) => c.path.endsWith("/defer"))?.body).toEqual({ reason: "Unterlagen fehlen" }));
  });

  it("composer is disabled while empty and posts a note", async () => {
    const { calls } = mockApi({
      ...workspaceRoutes(),
      "POST /cases/case-1/messages": { message: {}, analysis: { status: "OK", pending_message_ids: [], warnings: [] }, case: makeCase() },
    });
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: /Weitere Informationen aus dem Gespräch ergänzen/ }));
    const area = await screen.findByLabelText("Weitere Informationen aus dem Gespräch");
    const send = screen.getByRole("button", { name: /^Erfassen$/ });
    expect(send).toBeDisabled();
    await userEvent.type(area, "Es gibt noch einen Brief.");
    expect(send).toBeEnabled();
    await userEvent.click(send);
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toEqual({ content: "Es gibt noch einen Brief.", kind: "NOTE" }));
  });

  it("shows a simple escalation, details on demand, and no claim of contact", async () => {
    mockApi(
      workspaceRoutes({
        "GET /cases/case-1": makeCase({
          current_decision: escalateDecision,
          handover: { status: "RECOMMENDED", professional_types: ["employment_law_counsel"], reasons: [], requested_at: null, completed_at: null, completion_note: null },
        }),
      }),
    );
    renderApp("/cases/case-1");
    expect(await screen.findByText(/Prüfung durch eine Fachperson empfohlen/)).toBeInTheDocument();
    expect(await screen.findByText("Arbeitsrechtsberatung")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Fallbericht erstellen/ })).toBeInTheDocument();
    expect(screen.getByText(/Es wurde noch niemand kontaktiert/)).toBeInTheDocument();
    // technical details stay available on the second level
    const details = screen.getByTestId("decision-details");
    expect(details.closest("details")).not.toHaveAttribute("open");
    await userEvent.click(screen.getByText("Rechtliche Details ansehen"));
    expect(within(details).getByText("EMP_DEMO_DEADLINE_PENDING")).toBeInTheDocument();
    expect(within(details).getAllByText("DEADLINE_PENDING_EXPERT_REVIEW").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Als angefragt markieren" })).toBeInTheDocument();
  });

  it("surfaces a failed AI analysis with a retry, and does not show a fabricated next action", async () => {
    const { calls } = mockApi(
      workspaceRoutes({
        "GET /cases/case-1": makeCase({
          current_decision: null,
          analysis: { status: "FAILED", pending_message_ids: ["m1"], error_code: "ai_rate_limited", error_message: "Kontingent erreicht", warnings: [] },
        }),
        "POST /cases/case-1/analyze": makeCase(),
      }),
    );
    renderApp("/cases/case-1");
    const alert = await screen.findByText("Die KI-Analyse ist fehlgeschlagen.");
    expect(alert).toBeInTheDocument();
    expect(screen.queryByText("Nächste Rückfrage")).not.toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: /Erneut analysieren/ })[0]!);
    await waitFor(() => expect(calls.some((c) => c.path === "/cases/case-1/analyze")).toBe(true));
  });
});

describe("expert briefing", () => {
  it("renders all structured sections with unverified source labelling", () => {
    const view = { id: "b1", version: 2, case_version: 3, created_at: new Date().toISOString(), briefing } as unknown as BriefingView;
    render(<BriefingDocument view={view} />);
    for (const title of [
      "Fallübersicht",
      "Erkannte Rechtsgebiete",
      "Bekannte Fakten",
      "Fehlende Informationen",
      "Widersprüche und Unklarheiten",
      "Relevante Rechtsquellen",
      "Erkannte rechtliche Risiken",
      "Entscheidungsbegründung",
      "Eskalationsgründe",
      "Empfohlene Fachpersonen",
      "Nächste Schritte",
    ]) {
      expect(screen.getByRole("heading", { name: new RegExp(title) })).toBeInTheDocument();
    }
    expect(screen.getAllByText("Vom System nicht live verifiziert").length).toBeGreaterThan(0);
    expect(screen.getByText("Im Law-Dossier geprüft")).toBeInTheDocument();
    expect(screen.queryByText("Verifiziert")).not.toBeInTheDocument();
    expect(screen.getByText("Von KI extrahiert")).toBeInTheDocument();
    expect(screen.getByText(/Version 2/)).toBeInTheDocument();
    expect(screen.getByText(/nicht juristisch geprüft/)).toBeInTheDocument();
  });

  it("opens the latest briefing from the briefing route", async () => {
    mockApi({
      ...baseRoutes,
      "GET /cases/case-1": makeCase({ briefing_stale: false }),
      "GET /cases/case-1/briefings": [{ id: "b1", version: 1, case_version: 3, created_at: new Date().toISOString(), action: "ASK" }],
      "GET /cases/case-1/briefings/b1": { id: "b1", version: 1, case_version: 3, created_at: new Date().toISOString(), briefing },
    });
    renderApp("/cases/case-1/briefing");
    // new layout: A4 preview (server-rendered, sandboxed) + real PDF download; the old React view stays behind a toggle
    const frame = await screen.findByTitle("Fallbericht-Vorschau");
    expect(frame).toHaveAttribute("src", "/api/cases/case-1/briefings/b1/preview");
    expect(frame).toHaveAttribute("sandbox", expect.not.stringContaining("allow-scripts"));
    expect(screen.getByRole("link", { name: /PDF herunterladen/ })).toHaveAttribute("href", "/api/cases/case-1/briefings/b1/pdf");
    expect(await screen.findByText("Frühere Detailansicht (technisch)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fallbericht aktualisieren" })).toBeInTheDocument();
  });
});
