import { expect, test, type Page } from "@playwright/test";

/** Safety response + concrete referrals. MOCK provider only (no real AI). */

const RENT =
  "Meine Klientin hat in Zürich eine Wohnungskündigung erhalten. Sie ist alleinige Mieterin. Die Kündigung wurde ihr am 4. November 2026 mit normaler Post zugestellt. Laut ihrer Aussage wurde kein amtliches Kündigungsformular verwendet.";

async function describe(page: Page, text: string) {
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await page.getByLabel("Was ist passiert?").fill(text);
  await page.getByRole("button", { name: "Fall analysieren" }).click();
}

const emergency = (page: Page) => page.getByTestId("safety-emergency");

test("A: acute self-harm → emergency mode with 144, not a normal legal escalation", async ({ page }) => {
  await describe(page, "Ich werde aus dem Fenster springen.");
  const e = emergency(page);
  await expect(e).toBeVisible();
  await expect(e.getByRole("heading", { name: "Akute Gefahr erkannt – jetzt handeln" })).toBeVisible();
  await expect(e.getByRole("link", { name: /144 anrufen/ })).toHaveAttribute("href", "tel:144");
  await expect(e.getByText("Ergänzende Beratung (keine Notrufnummern)")).toBeVisible();
  await expect(e.getByRole("link", { name: /143 anrufen/ })).toHaveAttribute("href", "tel:143");
  await expect(e.getByRole("link", { name: /117 anrufen/ })).toHaveCount(0);
  await expect(e.getByText(/Den Anweisungen der Notrufstelle folgen/)).toBeVisible();
  // no misleading "bald", no report as the main action
  await expect(page.getByText("Dringlichkeit: bald").first()).toBeHidden(); // legal urgency only inside the collapsed secondary section
  await expect(page.getByRole("button", { name: "Fallbericht erstellen" })).not.toBeVisible();
  await expect(page.getByText("Akute Gefahr – Sicherheit klären").first()).toBeVisible();
  await page.screenshot({ path: "test-results/screens/safety-self-harm.png", fullPage: true });

  // survives a reload; the case list shows it too
  await page.reload();
  await expect(emergency(page)).toBeVisible();
  await page.goto("/");
  await expect(page.getByText("Akute Gefahr – Sicherheit klären").first()).toBeVisible();
});

test("B: violence threat → 117, 142 only as counselling", async ({ page }) => {
  await describe(page, "Mein Vermieter will mich schlagen und bedroht mich gerade.");
  const e = emergency(page);
  await expect(e.getByRole("link", { name: /117 anrufen/ }).first()).toHaveAttribute("href", "tel:117");
  const c142 = e.getByTestId("org-card").filter({ hasText: "Nationale Opferhilfe-Nummer" });
  await expect(c142.getByText("Beratung, keine Notrufnummer")).toBeVisible();
  await expect(e.getByText("Sofort Hilfe holen")).toBeVisible();
  await page.screenshot({ path: "test-results/screens/safety-violence.png", fullPage: true });
});

test("C: both dangers → both signals, 144 and 117", async ({ page }) => {
  await describe(page, "Mein Vermieter droht mich zu schlagen und ich werde aus dem Fenster springen.");
  const e = emergency(page);
  await expect(e.getByTestId("emergency-contacts").getByRole("link", { name: /144 anrufen/ })).toBeVisible();
  await expect(e.getByTestId("emergency-contacts").getByRole("link", { name: /117 anrufen/ })).toBeVisible();
  await expect(e).toContainText("Akute Selbstgefährdung");
  await expect(e).toContainText("Akute Gefahr / Gewaltandrohung");
  await page.screenshot({ path: "test-results/screens/safety-combined.png", fullPage: true });
});

test("rent case with a violence threat: emergency first, legal handling kept but secondary", async ({ page }) => {
  await describe(page, RENT + " Ihr Vermieter droht, sie zu schlagen.");
  await expect(emergency(page)).toBeVisible();
  const legal = page.getByTestId("legal-secondary");
  await expect(legal).toBeVisible();
  await expect(legal.getByRole("button", { name: "Fallbericht erstellen" })).not.toBeVisible(); // collapsed
  await legal.getByText("Juristische Fallbearbeitung (nachrangig").click();
  await expect(legal.getByRole("button", { name: "Fallbericht erstellen" })).toBeVisible();
  await emergency(page).getByText("Weiterführende Stellen nach der akuten Situation").click();
  await expect(emergency(page).getByText(/Opferberatung Zürich/).first()).toBeVisible();
});

test("documenting a response never clears the warning", async ({ page }) => {
  await describe(page, "Ich werde aus dem Fenster springen.");
  const e = emergency(page);
  await e.getByRole("button", { name: "Als bearbeitet dokumentieren" }).click();
  await e.getByLabel(/Was wurde veranlasst/).fill("Rettungsdienst 144 gerufen");
  await e.getByRole("button", { name: "Als bearbeitet dokumentieren" }).click();
  await expect(e.getByText(/Das ist keine Entwarnung/)).toBeVisible();
  await expect(e.getByRole("heading", { name: "Akute Gefahr erkannt – jetzt handeln" })).toBeVisible();
});

test("negation and plain legal text raise no alarm", async ({ page }) => {
  await describe(page, "Ich habe keine Suizidgedanken. " + RENT);
  await expect(page.getByRole("region", { name: "Einschätzung" })).toBeVisible();
  await expect(emergency(page)).toHaveCount(0);
});

test("normal legal escalation shows concrete organisations with real contact data", async ({ page }) => {
  await describe(page, RENT);
  const refs = page.getByTestId("referrals");
  await expect(refs).toBeVisible();
  const schlichtung = refs.getByTestId("org-card").filter({ hasText: "Bezirks Zürich" });
  // v1.2 (Law-Team-Korrektur): keine Telefonnummer der Schlichtungsbehörde; Kontakt über die offizielle Website
  await expect(schlichtung.getByRole("link", { name: /anrufen/ })).toHaveCount(0);
  await expect(schlichtung.getByRole("link", { name: "Website öffnen" })).toHaveAttribute("href", /^https:\/\/www\.gerichte-zh\.ch\//);
  await expect(schlichtung).toContainText("Offizielle Quelle");
  await expect(schlichtung).toContainText("Zuständig für Gemeinde Zürich, Bezirk Zürich");
  const mv = refs.getByTestId("org-card").filter({ hasText: "Mieterinnen- und Mieterverband" });
  await expect(mv.getByRole("link", { name: /044 296 90 20 anrufen/ })).toHaveAttribute("href", "tel:0442969020");
  await expect(mv).toContainText("Mo-Fr 09.00-12.00 und 13.30-17.00"); // phone remark moved out of the number, not lost
  await refs.getByText(/Weitere Anlaufstellen/).click();
  await expect(refs.getByText(/Rechtsauskunft in Miet- und Pachtsachen/)).toBeVisible();
  await page.screenshot({ path: "test-results/screens/referrals-zurich.png", fullPage: true });
});

test("Winterthur resolves the regional Mieterverband", async ({ page }) => {
  await describe(page, RENT.replace("Zürich", "Winterthur"));
  const refs = page.getByTestId("referrals");
  await expect(refs.getByText("Mieterverband Zürich, Beratungsstelle Winterthur").or(refs.getByText(/Winterthur/).first())).toBeVisible();
  await expect(refs).toContainText("Gemeinde Winterthur");
});

test("mobile emergency view: no overflow, call button reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await describe(page, "Mein Vermieter droht mich zu schlagen und ich werde aus dem Fenster springen.");
  await expect(emergency(page)).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const call = emergency(page).getByRole("link", { name: /144 anrufen/ });
  await expect(call).toBeInViewport();
  const box = await call.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(44);
  await page.screenshot({ path: "test-results/screens/safety-mobile.png", fullPage: true });
});
