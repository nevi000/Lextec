import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeCase } from "./fixtures";
import { errorResponse, kbStatusRoute, mockApi, renderApp, statusRoute } from "./test-utils";

const empty = makeCase({ issues: [], current_decision: null, analysis: { status: "OK", pending_message_ids: [], warnings: [] } });

const routes = (over: Record<string, unknown> = {}) => ({
  "GET /system/status": statusRoute,
  "GET /knowledge-base/status": kbStatusRoute,
  "GET /cases/case-1": empty,
  "GET /cases/case-1/messages": [],
  "GET /cases/case-1/facts": [],
  "GET /cases/case-1/decisions": [],
  "GET /cases/case-1/briefings": [],
  ...over,
});

const pdf = (name = "Fallbeschreibung.pdf") => new File(["%PDF-1.4 x"], name, { type: "application/pdf" });
const field = () => screen.getByLabelText("Was ist passiert?") as HTMLTextAreaElement;
const importer = () => screen.getByTestId("pdf-input") as HTMLInputElement;
const pdfOk = (text: string) => ({ "POST /intake/pdf-text": { text, pages: 1, truncated: false } });

/** A request that stays open until released, to look at the in-flight UI. */
function deferred() {
  let release!: (v: Response) => void;
  const promise = new Promise<Response>((r) => (release = r));
  return { promise, release };
}

describe("phase 1: Situation erfassen", () => {
  it("shows the new copy, placeholder and the PDF import hint; typing still works", async () => {
    mockApi(routes());
    renderApp("/cases/case-1");
    const f = await screen.findByLabelText("Was ist passiert?");
    expect(screen.getByText(/oder importieren Sie eine bereits verfasste Fallbeschreibung als PDF/)).toBeInTheDocument();
    expect(f).toHaveAttribute("placeholder", expect.stringContaining("Meine Klientin hat von ihrem Vermieter eine Kündigung erhalten"));
    expect(screen.getByText(/Vertragsunterlagen, Kündigungsschreiben und Belege werden hier nicht benötigt/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fallbeschreibung als PDF importieren" })).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: /Fall analysieren/ });
    expect(submit).toBeDisabled();
    await userEvent.type(f, "Meine Klientin hat eine Kündigung erhalten.");
    expect(submit).toBeEnabled();
  });

  it("keeps the text visible and read-only while analysing, shows the card, and allows no second request", async () => {
    const gate = deferred();
    const { calls } = mockApi(routes({ "POST /cases/case-1/messages": () => gate.promise }));
    renderApp("/cases/case-1");
    await userEvent.type(await screen.findByLabelText("Was ist passiert?"), "Meine Klientin hat eine Kündigung erhalten.");
    await userEvent.click(screen.getByRole("button", { name: /Fall analysieren/ }));

    const card = await screen.findByTestId("analysis-card");
    expect(card).toHaveTextContent("Fall wird analysiert");
    expect(field()).toHaveValue("Meine Klientin hat eine Kündigung erhalten.");
    expect(field()).toHaveAttribute("readonly");
    // honest steps: only the hand-over is done, the server step is running, the last one has not started
    const steps = card.querySelectorAll("li");
    expect([...steps].map((s) => s.getAttribute("data-state"))).toEqual(["done", "active", "waiting"]);
    expect(card.textContent).not.toMatch(/\d+\s?%/);
    expect(screen.queryByTestId("analysis-slow")).toBeNull();

    const busy = screen.getByRole("button", { name: /Analysiere/ });
    fireEvent.submit(busy.closest("form")!);
    fireEvent.keyDown(field(), { key: "Enter", ctrlKey: true });
    expect(calls.filter((c) => c.method === "POST" && c.path === "/cases/case-1/messages")).toHaveLength(1);
    gate.release(errorResponse(500, "x", "Test beendet"));
  });

  it("keeps the text and offers a retry when the request fails", async () => {
    let fail = true;
    const { calls } = mockApi(
      routes({
        "POST /cases/case-1/messages": () => (fail ? errorResponse(502, "ai_unavailable", "Gemini ist nicht erreichbar.") : errorResponse(500, "x", "ende")),
      }),
    );
    renderApp("/cases/case-1");
    await userEvent.type(await screen.findByLabelText("Was ist passiert?"), "Meine Klientin hat eine Kündigung erhalten.");
    await userEvent.click(screen.getByRole("button", { name: /Fall analysieren/ }));
    expect(await screen.findByText("Gemini ist nicht erreichbar.")).toBeInTheDocument();
    expect(screen.queryByTestId("analysis-card")).toBeNull();
    expect(field()).toHaveValue("Meine Klientin hat eine Kündigung erhalten.");
    expect(field()).not.toHaveAttribute("readonly");
    fail = true;
    await userEvent.click(screen.getByRole("button", { name: /Fall analysieren/ }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST" && c.path === "/cases/case-1/messages")).toHaveLength(2));
    expect(calls.filter((c) => c.path === "/cases/case-1/messages" && c.method === "POST")[1]!.body).toMatchObject({
      content: "Meine Klientin hat eine Kündigung erhalten.",
    });
  });
});

describe("phase 1: PDF import", () => {
  it("fills an empty field, confirms, and the text stays editable and analysable", async () => {
    const text = "Meine Klientin hat gestern eine Mietzinserhöhung erhalten.";
    const { calls } = mockApi(routes({ ...pdfOk(text), "POST /cases/case-1/messages": () => errorResponse(500, "x", "ende") }));
    renderApp("/cases/case-1");
    await screen.findByLabelText("Was ist passiert?");
    await userEvent.upload(importer(), pdf());
    await waitFor(() => expect(field()).toHaveValue(text));
    expect(screen.getByTestId("pdf-imported")).toHaveTextContent("Fallbeschreibung aus PDF übernommen");
    expect(screen.getByTestId("pdf-imported")).toHaveTextContent("Bitte überprüfen Sie den Text vor der Analyse.");
    // import = text only: no case/message request was made
    expect(calls.some((c) => c.path === "/cases/case-1/messages" && c.method === "POST")).toBe(false);

    await userEvent.type(field(), " Sie wohnt in Zürich.");
    expect(field()).toHaveValue(`${text} Sie wohnt in Zürich.`);
    await userEvent.click(screen.getByRole("button", { name: /Fall analysieren/ }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === "/cases/case-1/messages" && c.method === "POST")!.body).toMatchObject({
        content: `${text} Sie wohnt in Zürich.`,
        kind: "DESCRIPTION",
      }),
    );
  });

  it("never overwrites existing text silently: offers append / replace / cancel", async () => {
    mockApi(routes(pdfOk("Text aus dem PDF.")));
    renderApp("/cases/case-1");
    const f = await screen.findByLabelText("Was ist passiert?");
    await userEvent.type(f, "Bereits geschrieben.");
    await userEvent.upload(importer(), pdf());
    const group = await screen.findByRole("group", { name: "PDF-Text übernehmen" });
    expect(field()).toHaveValue("Bereits geschrieben."); // untouched while the choice is open
    expect(group).toHaveTextContent("Text aus PDF anhängen");

    await userEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(field()).toHaveValue("Bereits geschrieben.");

    await userEvent.upload(importer(), pdf());
    await userEvent.click(await screen.findByRole("button", { name: "Text aus PDF anhängen" }));
    expect(field()).toHaveValue("Bereits geschrieben.\n\nText aus dem PDF.");

    await userEvent.upload(importer(), pdf());
    await userEvent.click(await screen.findByRole("button", { name: "Bestehenden Text ersetzen" }));
    expect(field()).toHaveValue("Text aus dem PDF.");
  });

  it("shows the server error at once and keeps existing text", async () => {
    mockApi(
      routes({
        "POST /intake/pdf-text": () =>
          errorResponse(422, "pdf_no_text", "Aus diesem PDF konnte kein Text ausgelesen werden. Bitte verwenden Sie ein PDF mit auswählbarem Text."),
      }),
    );
    renderApp("/cases/case-1");
    await userEvent.type(await screen.findByLabelText("Was ist passiert?"), "Mein Text.");
    await userEvent.upload(importer(), pdf());
    expect(await screen.findByTestId("pdf-error")).toHaveTextContent("kein Text ausgelesen");
    expect(field()).toHaveValue("Mein Text.");
    // typing on manually still works, the button is usable again for another file
    await userEvent.type(field(), " Mehr.");
    expect(field()).toHaveValue("Mein Text. Mehr.");
    expect(screen.getByRole("button", { name: "Fallbeschreibung als PDF importieren" })).toBeEnabled();
  });

  it("is keyboard operable: the import button is a real, focusable button", async () => {
    mockApi(routes());
    renderApp("/cases/case-1");
    await screen.findByLabelText("Was ist passiert?");
    const b = screen.getByRole("button", { name: "Fallbeschreibung als PDF importieren" });
    b.focus();
    expect(b).toHaveFocus();
    expect(importer()).toHaveAttribute("accept", expect.stringContaining("pdf"));
  });
});
