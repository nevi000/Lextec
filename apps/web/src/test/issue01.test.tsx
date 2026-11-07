import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { IssueBriefingView } from "@/features/briefings/IssueBriefingView";
import { DEMO_STEPS, DEMO_TITLE } from "@/features/demo/demoScenario";
import type { DecisionResult, IssueBriefing } from "@/types";
import { askDecision, escalateDecision, knownFact, makeCase, missingFact } from "./fixtures";
import { kbStatusRoute, mockApi, renderApp, statusRoute } from "./test-utils";

const base = { "GET /system/status": statusRoute, "GET /knowledge-base/status": kbStatusRoute };

const withStatements = (over: Partial<DecisionResult> = {}) =>
  ({
    ...escalateDecision,
    max_urgency: "MEDIUM",
    approved_statements: [
      {
        rule_id: "TT_HINT_30_DAYS",
        issue_id: "CH_TENANCY_TERMINATION",
        text_de: "Eine Kündigung kann innert 30 Tagen nach Empfang bei der Schlichtungsbehörde angefochten werden.",
        source_ids: ["CH_OR_273_1"],
      },
    ],
    related_routes: [],
    statements_suppressed: false,
    ...over,
  }) as unknown as DecisionResult;

const msg = {
  id: "m1", role: "SOCIAL_WORKER", kind: "DESCRIPTION", content: "Der Vermieter hat gekündigt.", answers_fact_id: null,
  analysis_status: "DONE", analysis_error: null, created_at: new Date().toISOString(),
};

function workspace(decision: DecisionResult, title = "Kündigung durch die Vermieterschaft", messages: unknown[] = [msg]) {
  return {
    ...base,
    "GET /cases/case-1": makeCase({ title, current_decision: decision }),
    "GET /cases/case-1/messages": messages,
    "GET /cases/case-1/facts": [knownFact, missingFact],
    "GET /cases/case-1/decisions": [],
    "GET /cases/case-1/briefings": [],
  };
}

describe("asked-but-unknown", () => {
  it("«Weiss nicht» is recorded as unknown (explicit flag, no free text analysis)", async () => {
    const { calls } = mockApi({
      ...workspace(askDecision),
      "POST /cases/case-1/messages": { message: {}, analysis: { status: "OK", pending_message_ids: [], warnings: [] }, case: makeCase() },
    });
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: /Weiss nicht/ }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")).toBeDefined());
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({
      content: "Weiss nicht.",
      answers_fact_id: "employer_termination_in_writing",
      unknown: true,
    });
  });

  it("shows the unknown state separately from «not yet asked»", async () => {
    const unknownFact = { ...missingFact, status: "UNKNOWN", label_de: "Empfangsdatum" };
    mockApi({ ...workspace(askDecision), "GET /cases/case-1/facts": [unknownFact, { ...missingFact, label_de: "Objektart" }] });
    renderApp("/cases/case-1");
    await userEvent.click(await screen.findByRole("button", { name: /Alle Fallinformationen/ }));
    const panel = await screen.findByRole("region", { name: "Fallverständnis" });
    expect(await within(panel).findByText("Gefragt, unbekannt")).toBeInTheDocument();
    expect(within(panel).getByText("Offen (noch nicht gefragt)")).toBeInTheDocument();
  });
});

describe("controlled statements and urgency", () => {
  it("shows urgency in the dossier wording and only source-bound general hints", async () => {
    mockApi(workspace(withStatements()));
    renderApp("/cases/case-1");
    expect((await screen.findAllByText("Dringlichkeit: bald")).length).toBeGreaterThan(0);
    const panel = await screen.findByTestId("statements-panel");
    expect(panel).toHaveTextContent("innert 30 Tagen nach Empfang");
    expect(panel).toHaveTextContent("keine Rechtsberatung und keine Aussage über die Gültigkeit der Kündigung");
    expect(panel.textContent).not.toMatch(/bis (am|zum) \d{1,2}\./); // never a computed deadline end date
  });

  it("suppresses standard statements for cases outside the module", async () => {
    mockApi(workspace(withStatements({ statements_suppressed: true, approved_statements: [] })));
    renderApp("/cases/case-1");
    expect(await screen.findByText(/liegt ausserhalb des Moduls/)).toBeInTheDocument();
    expect(screen.queryByTestId("statements-panel")).not.toBeInTheDocument();
  });

  it("names a not-yet-available related issue honestly", async () => {
    mockApi(
      workspace(
        withStatements({
          related_routes: [
            { issue_id: "CH_TENANCY_PAYMENT_DEFAULT", title_de: "Kündigung wegen Zahlungsverzug (Issue 3)", available: false, note_de: "noch nicht juristisch freigegeben umgesetzt", from_rule_id: "TT_PAYMENT_DEFAULT" },
          ] as never,
        }),
      ),
    );
    renderApp("/cases/case-1");
    expect(await screen.findByText("noch nicht verfügbar")).toBeInTheDocument();
  });
});

describe("guided demo", () => {
  it("uses the real analysis pipeline: inserting a step only fills the normal input", async () => {
    const { calls } = mockApi(workspace(askDecision, DEMO_TITLE, []));
    renderApp("/cases/case-1");
    const guide = await screen.findByTestId("demo-guide");
    expect(guide).toHaveTextContent("Synthetische Demo-Daten");
    await userEvent.click(within(guide).getByRole("button", { name: "In Eingabefeld einfügen" }));
    expect((screen.getByLabelText(/Was ist passiert\?|Weitere Informationen aus dem Gespräch/) as HTMLTextAreaElement).value).toBe(
      DEMO_STEPS[0]!.text,
    );
    expect(calls.some((c) => c.method === "POST")).toBe(false); // nothing is analysed until the user submits
  });

  it("starts a demo case from the demo page", async () => {
    const { calls } = mockApi({
      ...base,
      "POST /cases": makeCase({ title: DEMO_TITLE }),
      "GET /cases/case-1": makeCase({ title: DEMO_TITLE }),
      "GET /cases/case-1/messages": [],
      "GET /cases/case-1/facts": [],
      "GET /cases/case-1/decisions": [],
      "GET /cases/case-1/briefings": [],
    });
    renderApp("/demo");
    await userEvent.click((await screen.findAllByRole("button", { name: /Demo starten/ }))[0]!);
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/cases")?.body).toEqual({ title: DEMO_TITLE }));
  });

  it("scenario texts match the documented four steps", () => {
    expect(DEMO_STEPS.map((s) => s.id)).toEqual([1, 2, 3, 4, 5]);
    expect(DEMO_STEPS[2]!.text).toContain("4. November 2026");
    expect(DEMO_STEPS[2]!.text).toContain("per 31. Januar 2027");
  });
});

const ib: IssueBriefing = {
  issue_id: "CH_TENANCY_TERMINATION",
  title_de: "Kündigung durch die Vermieterschaft",
  intro_de: "x",
  canton: "ZH",
  concern_de: "Die Klientin hat eine Kündigung erhalten.",
  groups: [
    {
      id: "delivery",
      title_de: "Zustellung und Empfang",
      rows: [
        { fact_id: "receipt_date", label_de: "Empfangsdatum", value_display: "04.11.2026", status: "KNOWN", evidence_level: "AI_EXTRACTED", evidence_label_de: "x", evidence_quote: "am 4. November 2026" },
        { fact_id: "delivery_method", label_de: "Art der Zustellung", value_display: "–", status: "UNKNOWN", evidence_level: "UNKNOWN", evidence_label_de: "x", evidence_quote: null },
        { fact_id: "official_form_used", label_de: "Amtliches Formular", value_display: "Nein", status: "KNOWN", evidence_level: "CONFIRMED", evidence_label_de: "x", evidence_quote: null },
        { fact_id: "termination_signed", label_de: "Unterschrieben", value_display: "Ja", status: "KNOWN", evidence_level: "DOCUMENTED", evidence_label_de: "x", evidence_quote: null },
        { fact_id: "rent_payer", label_de: "Zahlende Stelle", value_display: "–", status: "MISSING", evidence_level: "NOT_ASKED", evidence_label_de: "x", evidence_quote: null },
      ],
    },
  ],
  derived: [{ id: "days_since_earliest_receipt", label_de: "Tage seit dem frühesten bekannten Empfangshinweis", value: 3, evidence_level: "SYSTEM_DERIVED", note_de: "x" }],
  triggered_rules: [{ rule_id: "TT_FORM_MISSING", scope: "ISSUE", issue_id: "CH_TENANCY_TERMINATION", description: "d", reason_code: "POSSIBLE_FORM_DEFECT", reason_de: "Es wurde kein amtliches Kündigungsformular verwendet.", urgency: "MEDIUM", urgency_label_de: "bald" }],
  max_urgency: "MEDIUM",
  max_urgency_label_de: "bald",
  urgency_note_de: "Interne Dringlichkeitsbewertung. Das System nennt kein Fristende.",
  open_questions: ["Wohnt die Partnerperson noch dort?"],
  unknown_facts: ["Art der Zustellung"],
  documents_to_request: ["Kündigungsformular (beide Seiten)"],
  review_points: [{ text_de: "Form: Art. 266l–266o OR prüfen.", source_ids: ["CH_OR_266L"], triggered: true }],
  authorities: [
    { id: "A", name_de: "Schlichtungsbehörde in Miet- und Pachtsachen", purpose_de: "Anfechtung", cost_de: "Keine Gerichtskosten", scope_de: "", source_note_de: "", url_hint: "gerichte-zh.ch", contact_verified: false, verified_at: null, verification_note_de: "n" },
  ],
  statements_suppressed: false,
} as unknown as IssueBriefing;

function renderBriefing(value: IssueBriefing) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <IssueBriefingView ib={value} />
    </QueryClientProvider>,
  );
}

describe("issue-specific briefing", () => {
  it("separates every evidence level and never presents unverified contacts as current", () => {
    mockApi(base);
    renderBriefing(ib);
    const view = screen.getByTestId("issue-briefing");
    for (const label of ["Von KI extrahiert", "Gefragt, unbekannt", "Von Sozialarbeiterin bestätigt", "Dokumentarisch belegt", "Noch ungeklärt", "Systemseitig abgeleitet"]) {
      expect(within(view).getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(view).toHaveTextContent("TT_FORM_MISSING");
    expect(view).toHaveTextContent("Dringlichkeit: bald");
    expect(view).toHaveTextContent("kein Fristende");
    expect(within(view).getByText("Kontaktdaten nicht verifiziert")).toBeInTheDocument();
    expect(view).toHaveTextContent("Gefragt, aber unbekannt: Art der Zustellung");
    expect(view).toHaveTextContent("Anzufordernde Dokumente");
  });

  it("omits standard review points for cases outside the module", () => {
    mockApi(base);
    renderBriefing({ ...ib, statements_suppressed: true, review_points: [] });
    expect(screen.getByText(/ausserhalb des Moduls/)).toBeInTheDocument();
  });
});
