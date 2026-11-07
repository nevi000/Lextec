import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FedlexBadges, FedlexDetails } from "@/components/shared/SourceInfo";
import type { SourceRef } from "@/types";

type Info = NonNullable<SourceRef["fedlex"]>;

const base: Info = {
  origin: "FEDLEX",
  retrieval_status: "RETRIEVED",
  retrieval_label_de: "Amtlicher Text abgerufen",
  wording_status: "MATCHED",
  wording_label_de: "Wortlaut mit Wissensbasis abgeglichen",
  wording_details: {},
  interpretation_status: "NOT_REVIEWED",
  interpretation_label_de: "Interpretation: noch nicht durch das Law-Team geprüft",
  article_label: "Art. 266l",
  law_abbreviation: "OR",
  version_identifier: "20261001",
  valid_from: "2026-10-01",
  official_text: "1 Vermieter und Mieter müssen schriftlich kündigen.",
  official_article_url: "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de#art_266_l",
  official_document_url: "https://fedlex.data.admin.ch/filestore/x.xml",
  retrieved_at: "2026-11-07T10:00:00+00:00",
} as Info;

describe("Fedlex source display", () => {
  it("shows retrieval, wording and interpretation as separate honest statuses", () => {
    render(<FedlexBadges info={base} />);
    expect(screen.getByText("Amtlicher Text abgerufen")).toBeInTheDocument();
    expect(screen.getByText("Wortlaut mit Wissensbasis abgeglichen")).toBeInTheDocument();
    expect(screen.getByText(/noch nicht durch das Law-Team geprüft/)).toBeInTheDocument();
    expect(screen.queryByText(/Juristisch verifiziert/)).toBeNull();
  });

  it("renders version, official text and clickable official links", () => {
    render(<FedlexDetails info={base} />);
    expect(screen.getByText(/Fassung 20261001, gültig ab 2026-10-01/)).toBeInTheDocument();
    expect(screen.getByText(/schriftlich kündigen/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Artikel in Fedlex/ })).toHaveAttribute("href", base.official_article_url);
  });

  it("labels fixtures as test data, not as an official retrieval", () => {
    render(<FedlexDetails info={{ ...base, origin: "FIXTURE" }} />);
    expect(screen.getByText(/Testdaten \(Fixture\)/)).toBeInTheDocument();
  });

  it("shows a failed comparison honestly and no text for unretrieved sources", () => {
    const { container } = render(
      <FedlexDetails info={{ ...base, retrieval_status: "NOT_FOUND", message: "Quelle bei Fedlex nicht gefunden" }} />,
    );
    expect(container.textContent).toContain("nicht gefunden");
    expect(screen.queryByTestId("fedlex-details")).toBeNull();
  });
});
