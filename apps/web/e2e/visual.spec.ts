import { expect, test } from "@playwright/test";
import path from "node:path";

/** Captures the main screens at desktop and mobile widths into test-results/screens for visual review. */
const out = (name: string) => path.join("test-results", "screens", name);

for (const vp of [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test(`screens @ ${vp.name}`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/");
    await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
    await expect(page.getByLabel("Was ist passiert?")).toBeVisible();
    await page.screenshot({ path: out(`${vp.name}-workspace-empty.png`), fullPage: true });

    await page.getByLabel("Was ist passiert?").fill("Mein Arbeitgeber hat mir gekündigt.");
    await page.getByRole("button", { name: "Situation analysieren" }).click();
    await expect(page.getByRole("region", { name: "Nächste empfohlene Aktion" })).toBeVisible();
    await page.waitForTimeout(400); // let the entrance animation settle
    await page.screenshot({ path: out(`${vp.name}-workspace-ask.png`), fullPage: true });

    const caseUrl = page.url();
    await page.goto(`${caseUrl}/decision`);
    await expect(page.getByRole("heading", { name: "Entscheidungsbegründung" })).toBeVisible();
    await page.screenshot({ path: out(`${vp.name}-decision.png`), fullPage: true });

    await page.goto(`${caseUrl}/briefing`);
    await page.getByRole("button", { name: "Fallbericht erstellen", exact: true }).click();
    await expect(page.frameLocator('iframe[title="Fallbericht-Vorschau"]').getByText("Fallbericht").first()).toBeVisible();
    await page.waitForTimeout(500);
    await page.screenshot({ path: out(`${vp.name}-briefing.png`), fullPage: true });

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Meine Fälle" })).toBeVisible();
    await page.screenshot({ path: out(`${vp.name}-cases.png`), fullPage: true });
  });
}

test("escalation screen", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByRole("button", { name: "Neuen Fall erfassen" }).first().click();
  await page.getByLabel("Was ist passiert?").fill(
    "Mein Arbeitgeber hat mir gekündigt. Der Vermieter hat der Klientin ausserdem gekündigt, sie ist alleinerziehend.",
  );
  await page.getByRole("button", { name: "Situation analysieren" }).click();
  await expect(page.getByText(/Prüfung durch eine Fachperson empfohlen/)).toBeVisible();
  await page.screenshot({ path: out("desktop-workspace-escalate.png"), fullPage: true });
  await page.goto("/evaluation");
  await page.getByRole("button", { name: "Evaluation ausführen" }).click();
  await expect(page.getByText("Ergebnisse")).toBeVisible();
  await page.screenshot({ path: out("desktop-evaluation.png"), fullPage: true });
  await page.goto("/knowledge-base");
  await expect(page.getByText("Schema-Validierung bestanden")).toBeVisible();
  await page.screenshot({ path: out("desktop-knowledge-base.png"), fullPage: true });
});
