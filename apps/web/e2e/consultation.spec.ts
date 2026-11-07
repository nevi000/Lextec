import { expect, test, type Page } from "@playwright/test";

async function newCase(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Meine Fälle" })).toBeVisible();
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await expect(page.getByLabel("Was ist passiert?")).toBeVisible();
}

async function describe(page: Page, text: string) {
  await page.getByLabel("Was ist passiert?").fill(text);
  await page.getByRole("button", { name: "Fall analysieren" }).click();
}

const action = (page: Page) => page.getByRole("region", { name: "Nächste empfohlene Aktion" });

async function openAllInfo(page: Page) {
  await page.getByRole("button", { name: /Alle Fallinformationen/ }).click();
  return page.getByRole("region", { name: "Fallverständnis" });
}

test("start page is a plain case list: no dashboard cards, no technical navigation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Meine Fälle" })).toBeVisible();
  await expect(page.getByText("Hier finden Sie Ihre erfassten Beratungsfälle.")).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Hauptnavigation" });
  for (const hidden of ["Demo Mietkündigung", "Evaluation", "Knowledge Base", "Einstellungen", "Expert Briefings"]) {
    await expect(nav.getByText(hidden)).toHaveCount(0);
  }
  await expect(page.getByTestId("metrics")).toHaveCount(0);
});

test("ASK flow: describe → one question → answer → next question → persistence", async ({ page }) => {
  await newCase(page);
  await describe(page, "Mein Vermieter hat der Klientin die Wohnung gekündigt.");

  // recognised problem in plain words, ONE prominent question
  await expect(action(page).getByText(/Ist die Klientin selbst Mieterin laut Vertrag/)).toBeVisible();
  const summary = page.getByRole("region", { name: "Dieser Fall" });
  await expect(summary.getByText("Kündigung durch die Vermieterschaft")).toBeVisible();
  expect(await page.locator("main").innerText()).not.toMatch(/\d+ ?%|MISSING_REQUIRED_FACTS/);
  await expect(page.locator("main").getByRole("complementary")).toHaveCount(0); // no permanent technical side panel

  // answer → rules re-evaluated → next question
  await action(page).getByRole("radio", { name: /Klientin ist selbst Mieterin laut Vertrag/ }).click();
  await action(page).getByRole("button", { name: "Antwort speichern und weiter" }).click();
  await expect(action(page).getByText(/Ist die Klientin selbst Mieterin laut Vertrag/)).toHaveCount(0); // answered: next question
  await expect(action(page).getByRole("button", { name: /Weiss nicht/ })).toBeVisible();

  // facts live behind one click
  const panel = await openAllInfo(page);
  await expect(panel.getByText("Klientin ist selbst Mieterin laut Vertrag (Hauptmiete)").first()).toBeVisible();
  await page.getByRole("button", { name: "Schliessen" }).first().click();

  // «Weiss nicht» is stored as asked-but-unknown and not re-asked
  await action(page).getByRole("button", { name: /Weiss nicht/ }).click();
  await expect(page.getByText("Als «gefragt, aber unbekannt» erfasst").first()).toBeVisible();

  // briefing stays reachable (existing page and routes unchanged)
  const caseUrl = page.url();
  await page.goto(`${caseUrl}/briefing`);
  await page.getByRole("button", { name: "Fallbericht erstellen", exact: true }).click();
  const report = page.frameLocator('iframe[title="Fallbericht-Vorschau"]');
  await expect(report.getByText("Kündigung durch die Vermieterschaft").first()).toBeVisible();
  await expect(report.getByText(/Version 1/).first()).toBeVisible();

  // case remains available after a full reload, with a plain-language status
  await page.goto("/");
  await expect(page.getByRole("link", { name: /Kündigung durch die Vermieterschaft/ }).first()).toBeVisible();
  await expect(page.getByText(/Weitere Angaben nötig|In Bearbeitung|Fachperson empfohlen/).first()).toBeVisible();
  await page.goto(caseUrl);
  await expect(action(page)).toBeVisible();
});

test("ASK flow: a question can be deferred with a reason and the free text stays available", async ({ page }) => {
  await newCase(page);
  await describe(page, "Mein Vermieter hat der Klientin die Wohnung gekündigt.");
  await action(page).getByRole("button", { name: /Später beantworten/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Zurückstellen" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("mind. 3 Zeichen");
  await page.getByLabel("Grund für die Zurückstellung").fill("Unterlagen fehlen heute");
  await page.getByRole("dialog").getByRole("button", { name: "Zurückstellen" }).click();
  await expect(page.getByText("Frage zurückgestellt").first()).toBeVisible();

  await page.getByRole("button", { name: /Weitere Informationen aus dem Gespräch ergänzen/ }).click();
  await page.getByLabel("Weitere Informationen aus dem Gespräch").fill("Sie hat inzwischen einen eingeschriebenen Brief erhalten.");
  await page.getByRole("button", { name: /^Erfassen$/ }).click();
  await expect(page.getByText("Erfasst und analysiert").first()).toBeVisible();
});

test("ESCALATE flow: simple recommendation first, rule details one click away, honest handover state", async ({ page }) => {
  await newCase(page);
  await describe(
    page,
    "Der Vermieter hat der Klientin die Wohnung gekündigt, ohne amtliches Formular. Sie ist alleinerziehend.",
  );
  await expect(action(page).getByText(/Prüfung durch eine Fachperson empfohlen/)).toBeVisible();
  await expect(action(page).getByText("Mietrechtsberatung", { exact: true })).toBeVisible();
  await expect(action(page).getByText("Sozialberatung", { exact: true })).toBeVisible();
  await action(page).getByText("Übergabestatus verwalten").click();
  await expect(action(page).getByText(/Es wurde noch niemand kontaktiert/)).toBeVisible();

  // technical second level
  await expect(action(page).getByText("TT_HARDSHIP")).toBeHidden();
  await action(page).getByText("Rechtliche Details ansehen").click();
  await expect(action(page).getByText("TT_HARDSHIP")).toBeVisible();
  await expect(action(page).getByText("HARDSHIP_EXTENSION_AND_SOCIAL").first()).toBeVisible();

  const panel = await openAllInfo(page);
  await expect(panel.getByText("Kündigung durch die Vermieterschaft")).toBeVisible();
  await page.getByRole("button", { name: "Schliessen" }).first().click();

  await action(page).getByRole("button", { name: "Als angefragt markieren" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Als angefragt markieren" }).click();
  await expect(action(page).getByText(/Übergabe angefragt\. Bestätigen Sie sie/)).toBeVisible();
});

test("ESCALATE flow: unsupported legal area is not treated as understood", async ({ page }) => {
  await newCase(page);
  await describe(page, "Ich brauche Hilfe bei meiner Scheidung.");
  await expect(action(page).getByText(/Prüfung durch eine Fachperson empfohlen/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Dieser Fall" }).getByText(/nicht abgedeckt/).first()).toBeVisible();
  await action(page).getByText("Rechtliche Details ansehen").click();
  await expect(action(page).getByText("GLOBAL_UNSUPPORTED_ISSUE").first()).toBeVisible();
});

test("fact correction is visible, confirmed and survives new input", async ({ page }) => {
  await newCase(page);
  await describe(page, "Mein Vermieter hat der Klientin die Wohnung gekündigt, ohne amtliches Formular, in Zürich.");
  const panel = await openAllInfo(page);
  await panel.getByRole("button", { name: /Amtliches Kündigungsformular verwendet/ }).click();
  const dialog = page.getByRole("dialog").last();
  await dialog.getByLabel("Wert korrigieren oder ergänzen").selectOption("ja");
  await dialog.getByRole("button", { name: "Speichern" }).click();
  await expect(panel.getByText("Von Ihnen korrigiert")).toBeVisible();
  await expect(panel.getByText("Bestätigt")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: /Weitere Informationen aus dem Gespräch ergänzen/ }).click();
  await page.getByLabel("Weitere Informationen aus dem Gespräch").fill("Mein Vermieter hat gekündigt, ohne amtliches Formular, wie gesagt.");
  await page.getByRole("button", { name: "Erfassen", exact: true }).click();
  await expect(page.getByText("Erfasst und analysiert").first()).toBeVisible();
  const again = await openAllInfo(page);
  await expect(again.getByText("Von Ihnen korrigiert")).toBeVisible();
});

test("conversation history is secondary and opens on demand", async ({ page }) => {
  await newCase(page);
  await describe(page, "Mein Vermieter hat der Klientin die Wohnung gekündigt.");
  const history = page.getByTestId("timeline");
  await expect(history).not.toHaveAttribute("open", "");
  await history.getByText("Gesprächsverlauf anzeigen").click();
  await expect(history.getByText("Mein Vermieter hat der Klientin die Wohnung gekündigt.")).toBeVisible();
});

test("developer tools are outside the normal navigation but still available", async ({ page }) => {
  await page.goto("/dev");
  await expect(page.getByRole("heading", { name: "Entwicklerbereich" })).toBeVisible();
  await page.goto("/evaluation");
  await expect(page.getByText(/synthetisch-technisch/).first()).toBeVisible();
  await page.getByRole("button", { name: "Evaluation ausführen" }).click();
  await expect(page.getByText("Bestanden", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/juristisch validierte Szenarien/)).toBeVisible();
  await page.goto("/knowledge-base");
  await expect(page.getByText("Schema-Validierung bestanden")).toBeVisible();
  await expect(page.getByText(/0 \/ \d+ verifiziert/)).toBeVisible();
});
