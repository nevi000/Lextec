import { expect, test, type APIRequestContext } from "@playwright/test";

const TEXT = "Mein Vermieter hat meiner Klientin die Wohnung gekündigt, ohne amtliches Formular. Sie ist alleinerziehend mit zwei Kindern.";

/** Synthetic case set up through the real API (mock AI), then viewed in the real UI. */
async function makeCase(request: APIRequestContext, municipality: string): Promise<string> {
  const c = await (await request.post("/api/cases", { data: { title: "" } })).json();
  await request.post(`/api/cases/${c.id}/messages`, { data: { content: TEXT } });
  await request.post(`/api/cases/${c.id}/messages`, { data: { content: municipality, answers_fact_id: "property_municipality" } });
  return c.id as string;
}

test("Zürich case: Zürich conciliation authority and scope are shown in the real UI", async ({ page, request }) => {
  const id = await makeCase(request, "Zürich");
  await page.goto(`/cases/${id}`);
  const refs = page.getByTestId("referrals");
  await expect(refs.getByText(/Bezirks Zürich/).first()).toBeVisible();
  await expect(refs.getByText("Zuständig für Gemeinde Zürich, Bezirk Zürich").first()).toBeVisible();
});

test("Bülach case: district court Bülach, not Zürich; unverified social service is stated honestly", async ({ page, request }) => {
  const id = await makeCase(request, "Bülach");
  await page.goto(`/cases/${id}`);
  const refs = page.getByTestId("referrals");
  await expect(refs.getByText("Zuständig für Gemeinde Bülach, Bezirk Bülach").first()).toBeVisible();
  await expect(refs.getByText(/Bezirksgericht Bülach|Bülach/).first()).toBeVisible();
  await expect(refs.getByText(/Bezirks Zürich/)).toHaveCount(0);
  await page.getByText(/Weitere Anlaufstellen/).click();
  await expect(page.getByTestId("local-note").first()).toContainText("noch nicht einzeln geprüft");
  await page.screenshot({ path: "test-results/screens/referrals-buelach.png", fullPage: true });
});
