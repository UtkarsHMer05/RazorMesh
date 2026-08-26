// One-off visual capture for UI-11/UI-12/UI-17. Not a regression test;
// used during UI-17 polish + UI-18 handoff.
import { test, devices } from '@playwright/test';

const PAGES = [
  { url: '/', name: '01-landing-desktop' },
  { url: '/buyer', name: '02-buyer-desktop' },
  { url: '/security-lab', name: '03-seclab-desktop' },
  { url: '/audit', name: '04-audit-desktop' },
  { url: '/merchant', name: '05-merchant-desktop' },
] as const;

test.describe('snapshot', () => {
  test('desktop @ 1440x900', async ({ browser }) => {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    for (const p of PAGES) {
      await page.goto(p.url);
      await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
      await page.screenshot({
        path: `docs/ui-snapshots/${p.name}.png`,
        fullPage: true,
      });
    }
    await ctx.close();
  });

  test('mobile @ 390x844', async ({ browser }) => {
    const ctx = await browser.newContext({
      ...devices['iPhone 13'],
    });
    const page = await ctx.newPage();
    for (const p of PAGES) {
      await page.goto(p.url);
      await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
      await page.screenshot({
        path: `docs/ui-snapshots/${p.name}-mobile.png`,
        fullPage: true,
      });
    }
    await ctx.close();
  });
});
