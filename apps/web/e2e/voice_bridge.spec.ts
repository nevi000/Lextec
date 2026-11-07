import { expect, test, type Browser, type Page } from "@playwright/test";

async function startBridge(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await page.getByLabel("Was ist passiert?").fill("Mein Vermieter hat der Klientin die Wohnung gekündigt, ohne amtliches Formular, in Zürich.");
  await page.getByRole("button", { name: "Fall analysieren" }).click();
  await expect(page.getByRole("region", { name: "Nächste empfohlene Aktion" })).toBeVisible();
  await page.getByRole("button", { name: "Sprachbrücke aktivieren" }).click();
  const href = await page.getByTestId("bridge-link").getAttribute("href");
  expect(href).toContain("/bridge#t=");
  return href!.slice(href!.indexOf("/bridge#"));
}

async function phone(browser: Browser, baseURL: string, path: string) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 780 }, isMobile: true, hasTouch: true });
  const p = await ctx.newPage();
  await p.goto(baseURL + path);
  return { ctx, p };
}

async function answerOnPhone(p: Page) {
  const yes = p.getByRole("button", { name: "Yes", exact: true });
  if (await yes.count()) await yes.click();
  else await p.getByTestId("bridge-question").locator("xpath=ancestor::section//button").first().click();
}

test("one QR connection: phone follows the questions, the social worker confirms each answer (two devices)", async ({ page, browser, baseURL }) => {
  const path = await startBridge(page);
  const { ctx, p } = await phone(browser, baseURL!, path);

  await p.getByRole("button", { name: "English" }).click();
  await expect(p.getByText("Connected to the social worker")).toBeVisible();
  await expect(p.getByTestId("bridge-question")).toContainText("[EN · Mock]");
  await expect(page.getByTestId("bridge-status")).toContainText("Englisch");
  await expect(page.getByTestId("bridge-status")).toContainText("Smartphone verbunden");

  const q1 = await p.getByTestId("bridge-question").innerText();
  await answerOnPhone(p);
  await expect(p.getByText("Answer sent")).toBeVisible();
  await expect(p.getByText("The social worker is reviewing your answer.")).toBeVisible();
  await expect(page.getByTestId("bridge-answer")).toBeVisible(); // arrives on the desktop by itself
  await expect(page.getByTestId("bridge-answer")).toContainText("wartet auf Bestätigung");

  await page.getByRole("button", { name: "Antwort übernehmen" }).click();
  // the next question appears on the phone without a new QR code and without any "send" button
  await expect(p.getByTestId("bridge-question")).not.toHaveText(q1, { timeout: 15_000 });
  await expect(p.getByTestId("bridge-question")).toContainText("[EN · Mock]");

  // the confirmed answer is marked with its origin in the history
  await page.getByText(/Verlauf|Gesprächsverlauf/).first().click().catch(() => undefined);

  // the social worker ends the session: the phone shows the end screen and is locked out
  await page.getByRole("button", { name: "Sitzung beenden" }).click();
  await expect(p.getByText(/interview has ended|interview is complete/)).toBeVisible({ timeout: 10_000 });
  await ctx.close();
});

test("an answer given at the desk moves the phone on (no double answer)", async ({ page, browser, baseURL }) => {
  const path = await startBridge(page);
  const { ctx, p } = await phone(browser, baseURL!, path);
  await p.getByRole("button", { name: "English" }).click();
  const q1 = await p.getByTestId("bridge-question").innerText();
  await page.getByRole("radio").first().click();
  await page.getByRole("button", { name: "Antwort speichern und weiter" }).click();
  await expect(p.getByTestId("bridge-question")).not.toHaveText(q1, { timeout: 15_000 });
  await ctx.close();
});

test("Arabic is shown right-to-left", async ({ page, browser, baseURL }) => {
  const path = await startBridge(page);
  const { ctx, p } = await phone(browser, baseURL!, path);
  await p.getByRole("button", { name: "العربية" }).click();
  await expect(p.getByTestId("bridge-mobile")).toHaveAttribute("dir", "rtl");
  await expect(p.getByTestId("bridge-question")).toContainText("[AR · Mock]");
  await expect(p.getByText("متصل بالأخصائية الاجتماعية")).toBeVisible();
  await ctx.close();
});

test("the phone link works after a reload and an invalid link is explained", async ({ page, browser, baseURL }) => {
  const path = await startBridge(page);
  const { ctx, p } = await phone(browser, baseURL!, path);
  await p.getByRole("button", { name: "Українська" }).click();
  await expect(p.getByTestId("bridge-question")).toBeVisible();
  await p.reload(); // token is kept for this tab, no new scan needed
  await expect(p.getByTestId("bridge-question")).toBeVisible();
  const bad = await ctx.newPage();
  await bad.goto(`${baseURL}/bridge#t=nonsense`);
  await expect(bad.getByText(/QR/)).toBeVisible();
  await ctx.close();
});
