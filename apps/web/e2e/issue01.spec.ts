import { expect, test, type Page } from "@playwright/test";

/** Issue 1 (Kündigung durch die Vermieterschaft): the guided demo end to end, MOCK provider (no real AI). */

async function insertAndSend(page: Page, step: number) {
  const guide = page.getByTestId("demo-guide");
  await expect(guide.getByText(new RegExp(`Schritt ${step} –`))).toBeVisible();
  await guide.getByRole("button", { name: "In Eingabefeld einfügen" }).click();
  await page.getByRole("button", { name: /Situation analysieren|^Erfassen$/ }).click();
  await expect(page.getByText("Erfasst und analysiert").first()).toBeVisible();
}

test("guided demo: four steps through the real pipeline → escalation with rules → expert briefing → print", async ({
  page,
}) => {
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "Demo: Mietkündigung Zürich" })).toBeVisible();
  await page.screenshot({ path: "test-results/screens/demo-start.png", fullPage: true });
  await page.getByRole("button", { name: "Demo starten" }).first().click();
  await expect(page.getByTestId("demo-guide")).toBeVisible();
  await expect(page.getByTestId("demo-guide").getByText("Synthetische Demo-Daten")).toBeVisible();

  const action = page.getByRole("region", { name: "Nächste empfohlene Aktion" });
  const openInfo = async () => {
    await page.getByRole("button", { name: /Alle Fallinformationen/ }).click();
    return page.getByRole("region", { name: "Fallverständnis" });
  };

  // Step 1 – incomplete narrative: issue recognised, prioritised question with a reason
  await insertAndSend(page, 1);
  await expect(page.getByRole("region", { name: "Dieser Fall" }).getByText("Kündigung durch die Vermieterschaft")).toBeVisible();
  await expect(action.getByText("Ist die Klientin selbst Mieterin laut Vertrag")).toBeVisible();
  await action.getByText("Warum ist das wichtig?").click();
  await expect(action.getByText(/Nur die Vertragspartei hat den Kündigungsschutz/)).toBeVisible();

  // Step 2 – tenancy facts are added and never asked again
  await insertAndSend(page, 2);
  await expect(action.getByText(/Wie wurde die Kündigung zugestellt/)).toBeVisible();
  await expect(action.getByText("Ist die Klientin selbst Mieterin laut Vertrag")).toHaveCount(0);

  // Step 3 – delivery + form: possible form defect → human review, no verdict, no deadline end date
  await insertAndSend(page, 3);
  await expect(action.getByText(/Prüfung durch eine Fachperson empfohlen/)).toBeVisible();
  await expect(action.getByText("TT_FORM_MISSING")).toBeHidden(); // technical codes only on the second level
  await action.getByText("Rechtliche Details ansehen").click();
  await expect(action.getByText("TT_FORM_MISSING")).toBeVisible();
  await expect(action.getByText("POSSIBLE_FORM_DEFECT").first()).toBeVisible();
  await expect(page.getByText("Dringlichkeit: bald").first()).toBeVisible();
  await page.getByTestId("statements-panel").click();
  await expect(page.getByTestId("statements-panel")).toContainText("Ob hier ein Mangel vorliegt, soll eine Fachperson prüfen");
  await expect(page.getByTestId("statements-panel")).toContainText("keine Aussage über die Gültigkeit der Kündigung");
  const body = await page.locator("main").innerText();
  expect(body).not.toMatch(/04\.12\.2026|4\. Dezember 2026|Frist(ende)?:? .*2026/);
  expect(body).not.toMatch(/Kündigung ist (gültig|ungültig|nichtig)/);

  await page.waitForTimeout(500);
  await page.screenshot({ path: "test-results/screens/demo-step3-escalate.png", fullPage: true });

  // Step 4 – more context
  await insertAndSend(page, 4);
  // further questions are opt-in; asked-but-unknown is different from not-yet-asked
  const more = action.getByRole("button", { name: "Ergänzende Fragen beantworten" });
  if (await more.count()) {
    await more.click();
    await action.getByRole("button", { name: /Weiss nicht/ }).click();
    const info = await openInfo();
    await expect(info.getByText("Gefragt, unbekannt")).toBeVisible();
    await page.getByRole("button", { name: "Schliessen" }).first().click();
  }

  // Step 5 – expert briefing
  await page.getByTestId("demo-guide").getByRole("link", { name: "Expert Briefing öffnen" }).click();
  await page.getByRole("button", { name: "Fallbericht erstellen", exact: true }).click();
  const report = page.frameLocator('iframe[title="Fallbericht-Vorschau"]');
  await expect(report.getByText("Kündigung durch die Vermieterschaft").first()).toBeVisible();
  await expect(report.getByText("TT_FORM_MISSING").first()).toBeVisible();
  await expect(report.getByText("04.11.2026").first()).toBeVisible();
  await expect(report.getByText("31.01.2027").first()).toBeVisible();
  await expect(report.getByText("Hinweis, kein Fristende").first()).toBeVisible();
  await expect(report.getByText("Im Law-Dossier geprüft").first()).toBeVisible();
  await expect(report.getByText("Amtlicher Wortlaut abgerufen").first()).toBeVisible();
  const reportText = await report.locator("body").innerText();
  expect(reportText).not.toMatch(/04\.12\.2026|4\. Dezember 2026|Frist endet/); // never a computed deadline end date

  await page.screenshot({ path: "test-results/screens/demo-briefing.png", fullPage: true });

  // real PDF through the same route the download button uses (A4, several pages)
  const link = await page.getByRole("link", { name: /PDF herunterladen/ }).getAttribute("href");
  const res = await page.request.get(link!);
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toBe("application/pdf");
  expect((await res.body()).subarray(0, 4).toString()).toBe("%PDF");
});

test("Issue 1: unsupported mietverhältnis (Untermiete) is not answered with standard statements", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await page.getByLabel("Was ist passiert?").fill("Der Vermieter hat gekündigt. Die Klientin ist Untermieterin von Frau Meier.");
  await page.getByRole("button", { name: "Situation analysieren" }).click();
  const action = page.getByRole("region", { name: "Nächste empfohlene Aktion" });
  await action.getByText("Rechtliche Details ansehen").click();
  await expect(action.getByText("OUT_OF_SCOPE_NOT_MAIN_TENANT").first()).toBeVisible();
  await expect(page.getByText(/liegt ausserhalb des Moduls/)).toBeVisible();
  await expect(page.getByTestId("statements-panel")).toHaveCount(0);
});

test("Issue 1: hardship adds social counselling and an honest note about the not-yet-available issue", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await page.getByLabel("Was ist passiert?").fill("Der Vermieter hat gekündigt. Die Klientin ist alleinerziehend mit zwei Kindern.");
  await page.getByRole("button", { name: "Situation analysieren" }).click();
  const action = page.getByRole("region", { name: "Nächste empfohlene Aktion" });
  await expect(action.getByText("Mietrechtsberatung", { exact: true })).toBeVisible();
  await expect(action.getByText("Sozialberatung", { exact: true })).toBeVisible();
  await action.getByText("Rechtliche Details ansehen").click();
  await expect(action.getByText("TT_HARDSHIP")).toBeVisible();
  await expect(action.getByText("noch nicht verfügbar")).toBeVisible();
  await action.getByText("Übergabestatus verwalten").click();
  await expect(action.getByText(/Es wurde noch niemand kontaktiert/)).toBeVisible();
});

test("API usage stays visible and the app never needs a key in mock mode", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByText("Mock (lokal)")).toBeVisible();
  await expect(page.getByTestId("ai-usage")).toHaveCount(0); // only shown for the external provider
});
