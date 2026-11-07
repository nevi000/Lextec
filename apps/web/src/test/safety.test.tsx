import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { OrgCard } from "@/components/shared/OrgCard";
import { SafetyEmergency, SafetyNotice } from "@/features/consultation/SafetyPanel";
import { caseStatus } from "@/lib/caseStatus";
import type { ReferralCard, SafetyAssessment } from "@/types";

const base: ReferralCard = {
  id: "x", label: "Beispielstelle", type: "ngo", kind: "counselling", specializations: [],
  phones: [{ label_de: "Telefon", display: "044 111 22 33", tel: "0441112233" }],
  email: "info@example.ch", web: "https://example.ch/", address: "Teststrasse 1, 8000 Zürich", address_protected: false,
  hours: "Mo-Fr 9-12", costs: "kostenlos", access: "Terminpflicht", quality: "DIRECTORY",
  quality_label_de: "Kontaktangaben aus einem Fachverzeichnis; vor produktivem Einsatz auf der Website der Stelle bestätigen",
  verified: true, not_emergency_number: false,
} as ReferralCard;

const wrap = (ui: React.ReactNode) => (
  <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter>{ui}</MemoryRouter>
  </QueryClientProvider>
);

describe("OrgCard", () => {
  it("renders tel/https/mailto actions only from validated values", () => {
    render(<OrgCard org={base} />);
    expect(screen.getByRole("link", { name: /044 111 22 33 anrufen/ })).toHaveAttribute("href", "tel:0441112233");
    expect(screen.getByRole("link", { name: "Website öffnen" })).toHaveAttribute("href", "https://example.ch/");
    expect(screen.getByRole("link", { name: "E-Mail schreiben" })).toHaveAttribute("href", "mailto:info@example.ch");
    expect(screen.getByText(/vor produktivem Einsatz auf der Website der Stelle bestätigen/)).toBeInTheDocument();
  });

  it("never renders unsafe schemes as links", () => {
    render(<OrgCard org={{ ...base, web: "javascript:alert(1)", email: "x\"><script>@a.ch", phones: [{ label_de: "Telefon", display: "keine Nummer", tel: "javascript:1" }] }} />);
    expect(screen.queryByRole("link", { name: "Website öffnen" })).toBeNull();
    expect(screen.queryByRole("link", { name: "E-Mail schreiben" })).toBeNull();
    expect(document.querySelector("a[href^='javascript']")).toBeNull();
  });

  it("explains a protected address instead of showing one, and marks undocumented contacts", () => {
    render(<OrgCard org={{ ...base, address: null, address_protected: true, quality: "UNDOCUMENTED", verified: false, phones: [] }} />);
    expect(screen.getByText(/aus Schutzgründen nicht angegeben/)).toBeInTheDocument();
    expect(screen.getByText("Kontaktdaten nicht belegt")).toBeInTheDocument();
    expect(screen.getByText("Zuständigkeit noch nicht geprüft")).toBeInTheDocument();
  });

  it("labels counselling numbers that are not emergency lines", () => {
    render(<OrgCard org={{ ...base, not_emergency_number: true }} />);
    expect(screen.getByText("Beratung, keine Notrufnummer")).toBeInTheDocument();
  });
});

const emergency: SafetyAssessment = {
  state: "IMMEDIATE", signals: [{ id: "e1", category: "ACUTE_SELF_HARM", label_de: "Akute Selbstgefährdung", certainty: "ACUTE", action: "IMMEDIATE_SAFETY_RESPONSE", evidence_quote: "x", rule_id: "r", modifiers: [], acknowledged: false }],
  immediate_categories: ["ACUTE_SELF_HARM"], headline_de: "Akute Gefahr erkannt – jetzt handeln", explanation_de: "Bitte organisieren Sie jetzt geeignete Hilfe.",
  steps_de: ["Unverzüglich den Rettungsdienst (144) kontaktieren."],
  contacts_immediate: [{ ...base, id: "ambulance_144", label: "Sanität", type: "emergency", kind: "emergency", phones: [{ label_de: "Telefon", display: "144", tel: "144" }], web: null, email: null }],
  contacts_counselling: [{ ...base, id: "d143", label: "Die Dargebotene Hand", phones: [{ label_de: "Telefon", display: "143", tel: "143" }] }],
  contacts_further: [], briefing_flags: [], legal_secondary: true,
} as SafetyAssessment;

describe("SafetyEmergency", () => {
  it("shows an alert with the headline, the emergency number first and only opens the phone app", () => {
    render(wrap(<SafetyEmergency caseId="c1" safety={emergency} />));
    const alert = screen.getByRole("alert");
    expect(within(alert).getByRole("heading", { name: "Akute Gefahr erkannt – jetzt handeln" })).toBeInTheDocument();
    const call = within(alert).getByRole("link", { name: /144 anrufen/ });
    expect(call).toHaveAttribute("href", "tel:144");
    expect(within(alert).getByText("Ergänzende Beratung (keine Notrufnummern)")).toBeInTheDocument();
    expect(within(alert).queryByText(/Fallbericht/)).toBeNull(); // the report is never the main action here
  });

  it("documents handling without clearing the warning", () => {
    render(wrap(<SafetyEmergency caseId="c1" safety={{ ...emergency, signals: [{ ...emergency.signals[0]!, acknowledged: true, acknowledged_note: "144 gerufen" }] }} />));
    expect(screen.getByText(/144 gerufen/)).toBeInTheDocument();
    expect(screen.getByText(/keine Entwarnung/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Akute Gefahr erkannt – jetzt handeln" })).toBeInTheDocument();
  });
});

describe("SafetyNotice and status", () => {
  it("unclear signals stay calm: a hint, no emergency numbers", () => {
    render(wrap(<SafetyNotice caseId="c1" safety={{ ...emergency, state: "UNCLEAR", headline_de: "Mögliches Sicherheitssignal – bitte klären", explanation_de: "Bitte klären.", contacts_immediate: [], contacts_counselling: [] }} />));
    expect(screen.getByRole("status")).toHaveTextContent("Mögliches Sicherheitssignal");
    expect(screen.queryByRole("link", { name: /anrufen/ })).toBeNull();
  });

  it("the case list status puts an acute danger before any legal status", () => {
    expect(caseStatus({ status: "OPEN", current_action: "ESCALATE", handover_status: null, safety_state: "IMMEDIATE" }).label).toBe("Akute Gefahr – Sicherheit klären");
    expect(caseStatus({ status: "OPEN", current_action: "ESCALATE", handover_status: null, safety_state: "NONE" }).label).toBe("Fachperson empfohlen");
  });
});
