import { expect, test } from "@playwright/test";

test("home page communicates the trust core and mock-provider banner", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/RazorMesh Trust/i);
  const banner = page.getByTestId("mock-provider-banner");
  await expect(banner).toBeVisible();
  await expect(banner).toContainText(/no real money/i);
  await expect(
    page.getByRole("heading", { name: /intent-to-execution integrity/i }),
  ).toBeVisible();
});

test("primary nav reaches all five surfaces", async ({ page }) => {
  await page.goto("/");
  for (const [label, heading] of [
    ["Buyer", /buyer experience/i],
    ["Merchant", /merchant surface/i],
    ["Security Lab", /synthetic attack simulation/i],
    ["Audit", /audit dashboard/i],
  ] as const) {
    await page.getByRole("link", { name: label }).first().click();
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
});
