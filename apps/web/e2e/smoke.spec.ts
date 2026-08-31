import { expect, test } from '@playwright/test';

test('home page communicates the trust core and mock-provider banner', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/RazorMesh Trust/i);
  const banner = page.getByTestId('mock-provider-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText(/no real money/i);
  // The trust-core principle is exposed as a screen-reader-only section.
  await expect(
    page.getByRole('heading', { name: /intent-to-execution integrity/i }),
  ).toBeAttached();
  // The visible Bauhaus hero h1.
  await expect(
    page.getByRole('heading', { name: /transform/i, level: 1 }),
  ).toBeVisible();
});

test('landing nav links reach the real surfaces and sections', async ({
  page,
}) => {
  await page.goto('/');

  // The Bauhaus red "Get Started" CTA in the site nav reaches the buyer
  // surface. The shared nav is sticky on every page.
  await page.getByTestId('nav-cta').click();
  await expect(page).toHaveURL(/\/buyer$/);
  // The site nav remains available on the buyer page.
  await expect(page.getByTestId('nav-cta')).toBeVisible();
});

test('hero primary CTA reaches the real buyer surface', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('hero-primary-cta').click();
  await expect(page).toHaveURL(/\/buyer$/);
});

test('hero secondary CTA scrolls to the how-it-works section', async ({
  page,
}) => {
  await page.goto('/');
  await page.getByTestId('hero-secondary-cta').click();
  await expect(page).toHaveURL(/\/#how$/);
  // The "How it works" section heading is in the DOM and on-screen.
  await expect(
    page.getByRole('heading', { name: /five steps from human intent/i }),
  ).toBeInViewport();
});

test('security lab preview CTA reaches the real security-lab surface', async ({
  page,
}) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Open Security Lab' }).click();
  await expect(page).toHaveURL(/\/security-lab$/);
  await expect(
    page.getByRole('heading', { name: /synthetic attack simulation/i }),
  ).toBeVisible();
});

test('footer nav reaches the real audit surface', async ({ page }) => {
  await page.goto('/');
  await page
    .getByRole('contentinfo')
    .getByRole('link', { name: 'Audit' })
    .click();
  await expect(page).toHaveURL(/\/audit$/);
});

test('protocols page renders the Phase-4 gateway dashboard', async ({ page }) => {
  await page.goto('/protocols');
  await expect(
    page.getByRole('heading', { name: /protocol gateway/i, level: 2 }).first(),
  ).toBeVisible();
  await expect(page.getByText(/FINAL (ALLOW|CHALLENGE|BLOCK)/i)).toBeVisible();
  await expect(page.getByText(/UCP 2026-04-08/)).toBeVisible();
  await expect(page.getByText(/AP2 v0\.2\.0/)).toBeVisible();
  await expect(
    page.getByRole('heading', { name: /AgentPay-X results/i, level: 2 }),
  ).toBeVisible();
});
