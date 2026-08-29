// OVN039/040/041 — responsive overlap + console/network + keyboard/reduced-motion sweep.
// Read-only verification; screenshots written to docs/agentpay_ir_v2/evidence/sweep/.
// Run: node scripts/ovn_browser_sweep.mjs
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("../apps/web/node_modules/@playwright/test");
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = process.env.SWEEP_BASE ?? "http://localhost:3000";
const OUT = "docs/agentpay_ir_v2/evidence/sweep";
mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [
  { name: "390x844", width: 390, height: 844 },
  { name: "430x932", width: 430, height: 932 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1280x800", width: 1280, height: 800 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const ROUTES = ["/", "/buyer", "/protocols", "/security-lab", "/audit", "/merchant"];

const report = { generated_at: new Date().toISOString(), base: BASE, checks: [] };

function intersect(a, b) {
  const x = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
  const y = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
  return x * y;
}

const browser = await chromium.launch();
try {
  for (const route of ROUTES) {
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await context.newPage();
      const consoleErrors = [];
      const failedRequests = [];
      page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 300)); });
      page.on("requestfailed", (r) => failedRequests.push(`${r.url().slice(0, 120)} :: ${r.failure()?.errorText ?? "?"}`));
      page.on("response", (r) => { if (r.status() >= 500) failedRequests.push(`${r.url().slice(0, 120)} :: HTTP ${r.status()}`); });

      await page.goto(BASE + route, { waitUntil: "domcontentloaded", timeout: 30000 });
      await page.waitForTimeout(1600);

      // OVN039: horizontal scroll check
      const hscroll = await page.evaluate(() => {
        const de = document.documentElement;
        return { scrollWidth: de.scrollWidth, clientWidth: de.clientWidth };
      });
      const hscrollOk = hscroll.scrollWidth <= hscroll.clientWidth + 1;

      // OVN039: critical-control visibility + pairwise overlap of interactive elements
      const ctl = await page.evaluate(() => {
        const intersect = (a, b) => {
          const x = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
          const y = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
          return x * y;
        };
        const sels = [
          "nav a", "nav button",
          "button:not([disabled])", "input:not([type=hidden]):not([disabled])",
          "textarea:not([disabled])", "[role=radio]",
        ];
        const nodes = [];
        for (const sel of sels) {
          for (const el of document.querySelectorAll(sel)) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) {
              nodes.push({ tag: el.tagName, name: (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 40), box: { x: r.x, y: r.y, width: r.width, height: r.height }, inViewport: r.y < innerHeight && r.y + r.height > 0 });
            }
          }
        }
        const overlaps = [];
        const parents = new Set();
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const a = nodes[i].box, b = nodes[j].box;
            const ar = intersect(a, b);
            const minArea = Math.min(a.width * a.height, b.width * b.height);
            // overlap is a defect only if it covers >25% of the smaller control and neither contains the other
            const contains = (a.x <= b.x && a.y <= b.y && a.x + a.width >= b.x + b.width && a.y + a.height >= b.y + b.height) || (b.x <= a.x && b.y <= a.y && b.x + b.width >= a.x + a.width && b.y + b.height >= a.y + a.height);
            if (ar > minArea * 0.25 && !contains) {
              overlaps.push([nodes[i], nodes[j], Math.round(ar)]);
            }
          }
        }
        // text clipping proxy: any element scrolled out horizontally
        let clippedText = 0;
        for (const el of document.querySelectorAll("h1,h2,h3,button,a,p,li,td,th,label")) {
          if (el.scrollWidth > el.clientWidth + 4 && getComputedStyle(el).overflowX !== "visible" && el.clientWidth > 0) clippedText++;
        }
        return { count: nodes.length, overlaps: overlaps.map(([a, b, ar]) => ({ a: a.tag + ":" + a.name, b: b.tag + ":" + b.name, area: ar })), clippedText };
      });

      if (vp.name === "1440x900" || vp.name === "390x844") {
        await page.screenshot({ path: `${OUT}/${route.replace(/\//g, "_")}_${vp.name}.png`, fullPage: false });
      }

      report.checks.push({
        route, viewport: vp.name,
        horizontal_scroll: hscroll,
        horizontal_scroll_ok: hscrollOk,
        interactive_elements: ctl.count,
        overlaps: ctl.overlaps,
        clipped_text_elements: ctl.clippedText,
        console_errors: consoleErrors,
        failed_requests: failedRequests,
      });
      await context.close();
    }
  }

  // OVN041: keyboard navigation on /buyer (Tab reaches textarea + compile btn)
  {
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();
    await page.goto(BASE + "/buyer", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    const order = [];
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press("Tab");
      order.push(await page.evaluate(() => {
        const el = document.activeElement;
        return el ? `${el.tagName}:${(el.getAttribute("data-testid") ?? el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 30)}` : "none";
      }));
    }
    report.keyboard_buyer_tab_order = order;

    // Enter on focused textarea works (typing reaches it)
    await page.getByTestId("nl-input").focus();
    await page.keyboard.type("buy headphones under 5000");
    const typed = await page.getByTestId("nl-input").inputValue();
    report.keyboard_textarea_input_works = typed.includes("headphones");

    // OVN041: reduced motion
    const rcontext = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" });
    const rpage = await rcontext.newPage();
    await rpage.goto(BASE + "/", { waitUntil: "domcontentloaded" });
    await rpage.waitForTimeout(1200);
    report.reduced_motion_renders = (await rpage.title()).includes("RazorMesh");
    await rpage.screenshot({ path: `${OUT}/reduced_motion_home.png` });
    await rcontext.close();
    await context.close();
  }
} finally {
  await browser.close();
}

writeFileSync("docs/agentpay_ir_v2/evidence/OVN039_040_041_sweep.json", JSON.stringify(report, null, 2));
const bad = report.checks.filter(c => !c.horizontal_scroll_ok || c.overlaps.length > 0 || c.console_errors.length > 0 || c.failed_requests.length > 0);
console.log(JSON.stringify({
  total_checks: report.checks.length,
  horizontal_scroll_failures: report.checks.filter(c => !c.horizontal_scroll_ok),
  overlap_failures: report.checks.filter(c => c.overlaps.length > 0),
  console_error_checks: report.checks.filter(c => c.console_errors.length > 0),
  failed_request_checks: report.checks.filter(c => c.failed_requests.length > 0),
  clipped_text_max: Math.max(...report.checks.map(c => c.clipped_text_elements)),
  keyboard_buyer_tab_order: report.keyboard_buyer_tab_order,
  keyboard_textarea_input_works: report.keyboard_textarea_input_works,
  reduced_motion_renders: report.reduced_motion_renders,
}, null, 1));
