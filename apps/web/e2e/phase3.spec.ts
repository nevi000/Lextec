import { expect, test, type Page } from "@playwright/test";

/** Phase 3: assessment, optional supplement, and the case report. MOCK provider only (no real AI). */

const RENT =
  "Meine Klientin hat in Zürich eine Wohnungskündigung erhalten. Sie ist alleinige Mieterin. Die Kündigung wurde ihr am 4. November 2026 mit normaler Post zugestellt. Laut ihrer Aussage wurde kein amtliches Kündigungsformular verwendet.";
const FULL =
  RENT +
  " Der Vertrag ist unbefristet, es ist eine normale Wohnung, keine Untermiete. Die Kündigung soll per 31. Januar 2027 gelten. Die Klientin hat keine Mietrückstände, keine Mitmieter und keine Ehe- oder eingetragene Partnerperson in der Wohnung. Sie hat nichts unterschrieben und keine Anfechtung eingereicht.";

async function start(page: Page, text: string, expectPhase3 = true) {
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  // new case: calm start, no warning status before the first input
  await expect(page.getByLabel("Was ist passiert?")).toBeVisible();
  await expect(page.getByText("Weitere Angaben nötig")).toHaveCount(0);
  await page.getByLabel("Was ist passiert?").fill(text);
  await page.getByRole("button", { name: "Fall analysieren" }).click();
  if (expectPhase3) await expect(page.getByRole("region", { name: "Einschätzung" })).toBeVisible();
  else await expect(page.getByText("Erfasst und analysiert").first()).toBeVisible();
}

test("new case starts calm: no status before the first analysis and a clean list entry", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await expect(page.getByLabel("Was ist passiert?")).toBeVisible();
  await expect(page.getByRole("img", { name: "LexTec" })).toBeVisible(); // official logo, served locally
  await page.screenshot({ path: "test-results/screens/new-case.png", fullPage: true });
  await page.goto("/");
  await expect(page.getByText("Noch nicht gestartet").first()).toBeVisible();
});

test("phase 3 has three clear areas; the report is created without contacting anybody", async ({ page }) => {
  await start(page, RENT);
  const sections = page.getByRole("region", { name: "Nächste empfohlene Aktion" });
  await expect(sections.getByRole("region", { name: "Einschätzung" })).toBeVisible();
  await expect(sections.getByRole("region", { name: "Ergänzende Angaben (optional)" })).toBeVisible();
  await expect(sections.getByRole("region", { name: "Fallbericht" })).toBeVisible();
  await expect(sections.getByText("Möchten Sie den Fall noch ergänzen?")).toBeVisible();
  await expect(sections.getByText(/Mietrechtsberatung/).first()).toBeVisible();
  // free text is not permanently visible in phase 3
  await expect(page.getByLabel("Weitere Informationen aus dem Gespräch")).toHaveCount(0);
  await page.screenshot({ path: "test-results/screens/phase3-normal.png", fullPage: true });

  // report ≠ handover
  await sections.getByRole("button", { name: "Fallbericht erstellen" }).click();
  await expect(page.frameLocator('iframe[title="Fallbericht-Vorschau"]').getByText("Fallbericht").first()).toBeVisible();
  await expect(page.getByLabel("Briefing-Version").locator("option")).toHaveCount(1);
  await page.getByRole("link", { name: /Zurück zum Fall/ }).click();
  await expect(sections.getByRole("link", { name: "Fallbericht ansehen" })).toBeVisible();
  await sections.getByText("Übergabestatus verwalten").click();
  await expect(sections.getByText(/Übergabe empfohlen\. Es wurde noch niemand kontaktiert/)).toBeVisible();
});

test("optional questions: opt-in, one at a time, skippable, endable; report stays reachable", async ({ page }) => {
  await start(page, FULL);
  const sections = page.getByRole("region", { name: "Nächste empfohlene Aktion" });
  const supplement = sections.getByRole("region", { name: "Ergänzende Angaben (optional)" });
  const open = supplement.getByRole("button", { name: "Ergänzende Fragen beantworten" });
  await expect(sections.getByRole("button", { name: "Fallbericht erstellen" })).toBeEnabled();
  if ((await open.count()) === 0) {
    await expect(supplement.getByText(/keine ergänzenden Fragen offen/)).toBeVisible();
    return;
  }
  await expect(supplement.getByText(/ergänzende Frage(n)? verfügbar/)).toBeVisible();
  await open.click();
  await expect(supplement.getByRole("button", { name: "Antwort speichern und weiter" })).toBeVisible();
  await page.screenshot({ path: "test-results/screens/phase3-optional.png", fullPage: true });
  await supplement.getByRole("button", { name: "Überspringen" }).click();
  // the next question follows (one at a time); if none is left the area returns to its calm state by itself
  const end = supplement.getByRole("button", { name: "Ergänzung beenden" });
  await expect(end.or(supplement.getByText(/keine ergänzenden Fragen offen/))).toBeVisible();
  await end.click({ timeout: 3000 }).catch(() => undefined); // may already have returned to the calm state
  await expect(supplement.getByRole("button", { name: "Antwort speichern und weiter" })).toHaveCount(0);
  await expect(sections.getByRole("button", { name: "Fallbericht erstellen" })).toBeEnabled();
});

test("urgent case: the human action is explicit and never hidden behind the report", async ({ page }) => {
  // unknown delivery is a HIGH-urgency rule (start of the deadline cannot be determined)
  await start(page, "Die Klientin hat eine Wohnungskündigung in Zürich erhalten, weiss aber nicht, wann und wie sie zugestellt wurde. Sie ist alleinige Mieterin einer normalen Wohnung in der Stadt Zürich. Der Vertrag ist unbefristet. Es ist keine Untermiete und keine Ferienwohnung.", false);
  const sections = page.getByRole("region", { name: "Nächste empfohlene Aktion" });
  // answer every question with «Weiss nicht» until the backend reaches its (urgent) assessment
  for (let i = 0; i < 12 && (await page.getByRole("region", { name: "Einschätzung" }).count()) === 0; i++) {
    await sections.getByRole("button", { name: /Weiss nicht/ }).click();
    await expect(page.getByText("gefragt, aber unbekannt").first()).toBeVisible();
    await page.waitForTimeout(400);
  }
  const alert = page.getByRole("alert").filter({ hasText: "Dringend" });
  await expect(alert).toContainText("umgehend Kontakt mit einer geeigneten Fachperson", { timeout: 15000 });
  await expect(alert).toContainText("Fallbericht ersetzt diese Kontaktaufnahme nicht");
  await expect(sections.getByText("Dringende Prüfung durch eine Fachperson empfohlen")).toBeVisible();
  await page.screenshot({ path: "test-results/screens/phase3-urgent.png", fullPage: true });
  await expect(page.getByRole("button", { name: "Fallbericht erstellen" })).toBeVisible();
});

test("existing report: new information makes it stale, update creates a new version and keeps the old one", async ({ page }) => {
  await start(page, RENT);
  const sections = page.getByRole("region", { name: "Nächste empfohlene Aktion" });
  await sections.getByRole("button", { name: "Fallbericht erstellen" }).click();
  await expect(page.frameLocator('iframe[title="Fallbericht-Vorschau"]').getByText("Fallbericht").first()).toBeVisible();
  await page.getByRole("link", { name: /Zurück zum Fall/ }).click();

  // free text on demand through the normal pipeline
  await sections.getByRole("button", { name: "Andere Informationen ergänzen" }).click();
  await page.getByLabel("Weitere Informationen aus dem Gespräch").fill("Die Klientin hat keine Mietrückstände.");
  await page.getByRole("button", { name: /^Erfassen$/ }).click();
  await expect(page.getByText("Erfasst und analysiert").first()).toBeVisible();

  await expect(sections.getByText(/Seit dem letzten Fallbericht wurden neue Angaben erfasst/)).toBeVisible();
  await sections.getByRole("button", { name: "Fallbericht aktualisieren" }).click();
  await expect(page.frameLocator('iframe[title="Fallbericht-Vorschau"]').getByText("Fallbericht").first()).toBeVisible();
  const versions = page.getByLabel("Briefing-Version");
  await expect(versions.locator("option")).toHaveCount(2); // old version preserved
});

test("mobile: no horizontal overflow in phase 3 and the report action is reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await start(page, RENT);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const btn = page.getByRole("button", { name: "Fallbericht erstellen" });
  await btn.scrollIntoViewIfNeeded();
  await expect(btn).toBeInViewport();
  await page.screenshot({ path: "test-results/screens/mobile-phase3.png", fullPage: true });
});
