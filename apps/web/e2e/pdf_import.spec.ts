import { expect, test, type Page } from "@playwright/test";

/** Minimal synthetic text PDF (one line, WinAnsi) – contains only a made-up case description. */
function textPdf(line: string): Buffer {
  const content = `BT /F1 12 Tf 50 750 Td (${line}) Tj ET`;
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
  ];
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objs.forEach((o, i) => {
    offsets.push(out.length);
    out += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets) out += `${String(off).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

async function newCase(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await expect(page.getByLabel("Was ist passiert?")).toBeVisible();
}

const TEXT = "Meine Klientin hat gestern eine Mietzinserhöhung erhalten. Sie wohnt in Zürich.";

test("PDF import fills the field, text is editable, then the normal analysis runs (Issue 7)", async ({ page }) => {
  await newCase(page);
  await page.getByTestId("pdf-input").setInputFiles({ name: "Fallbeschreibung.pdf", mimeType: "application/pdf", buffer: textPdf(TEXT) });
  const field = page.getByLabel("Was ist passiert?");
  await expect(field).toHaveValue(TEXT);
  await expect(page.getByTestId("pdf-imported")).toContainText("Bitte überprüfen Sie den Text vor der Analyse.");

  await field.pressSequentially(" Sie möchte die Erhöhung prüfen lassen.");
  await page.getByRole("button", { name: "Fall analysieren" }).click();
  await expect(page.getByRole("region", { name: "Dieser Fall" }).getByText(/Mietzins/).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Nächste empfohlene Aktion" })).toBeVisible();
});

test("existing text is kept: append or replace is offered; invalid PDF shows an error", async ({ page }) => {
  await newCase(page);
  const field = page.getByLabel("Was ist passiert?");
  await field.fill("Bereits geschrieben.");
  await page.getByTestId("pdf-input").setInputFiles({ name: "a.pdf", mimeType: "application/pdf", buffer: textPdf("Text aus PDF.") });
  await expect(page.getByRole("group", { name: "PDF-Text übernehmen" })).toBeVisible();
  await expect(field).toHaveValue("Bereits geschrieben.");
  await page.getByRole("button", { name: "Text aus PDF anhängen" }).click();
  await expect(field).toHaveValue("Bereits geschrieben.\n\nText aus PDF.");

  await page.getByTestId("pdf-input").setInputFiles({ name: "kaputt.pdf", mimeType: "application/pdf", buffer: Buffer.from("das ist kein pdf") });
  await expect(page.getByTestId("pdf-error")).toContainText("kein PDF");
  await expect(field).toHaveValue("Bereits geschrieben.\n\nText aus PDF.");
});
