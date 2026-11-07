import { expect, test } from "@playwright/test";

/** Synthetic rent-termination case → ESCALATE → briefing shows Art. 266l / 266o OR with honest source status.
 *  The cache holds FIXTURE snapshots (labelled as test data); no network, no real AI. */

const TEXT =
  "Meine Klientin hat in Zürich eine Wohnungskündigung erhalten. Sie ist alleinige Mieterin. Die Kündigung wurde ihr am 4. November 2026 mit normaler Post zugestellt. Laut ihrer Aussage wurde kein amtliches Kündigungsformular verwendet.";

test("rent termination: ESCALATE, and the briefing shows Art. 266l and 266o OR with transparent source status", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await page.getByLabel("Was ist passiert?").fill(TEXT);
  await page.getByRole("button", { name: "Fall analysieren" }).click();

  const action = page.getByRole("region", { name: "Nächste empfohlene Aktion" });
  await expect(action.getByText(/Prüfung durch eine Fachperson empfohlen/)).toBeVisible();
  await action.getByText("Rechtliche Details ansehen").click();
  await expect(action.getByText("TT_FORM_MISSING")).toBeVisible();

  // compact source chips in the workspace carry their status in the tooltip, never "verified"
  await page.getByTestId("statements-panel").click();
  await expect(page.getByTestId("statements-panel")).not.toContainText("Juristisch verifiziert");

  // Phase 3: «Übergabe vorbereiten» creates the briefing through the existing API and opens it
  await action.getByRole("button", { name: "Fallbericht erstellen" }).click();
  const report = page.frameLocator('iframe[title="Fallbericht-Vorschau"]');
  await expect(report.getByText("Art. 266l").first()).toBeVisible();
  await expect(report.getByText("Art. 266o").first()).toBeVisible();
  await expect(report.getByText("Testdaten (kein amtlicher Abruf)").first()).toBeVisible();
  await expect(report.getByText(/Interpretation noch nicht freigegeben/).first()).toBeVisible();
  const text = await report.locator("body").innerText();
  expect(text).not.toContain("Juristisch verifiziert");
  expect(text).not.toMatch(/04\.12\.2026|4\. Dezember 2026/); // never a computed deadline end date
  expect((text.split("Dokumentenverzeichnis")[0] ?? "").split("Rechtsquellen")[0] ?? "").not.toMatch(/Kündigung ist (gültig|ungültig|nichtig)/); // statute quotes live in the annex

  await page.screenshot({ path: "test-results/screens/fedlex-briefing-sources.png", fullPage: true });
  const link = await page.getByRole("link", { name: /PDF herunterladen/ }).getAttribute("href");
  const res = await page.request.get(link!);
  expect(res.status()).toBe(200);
  expect((await res.body()).length).toBeGreaterThan(20_000);
});
