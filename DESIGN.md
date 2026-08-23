# DESIGN.md — RazorMesh Trust Design System

## 1. Design objective

RazorMesh should feel native to a modern Razorpay/agentic-finance context without pretending to be an official Razorpay product.

The design should communicate:

- trust;
- clarity;
- deliberate financial state;
- calm warnings;
- visible reasoning;
- precise action boundaries;
- modern AI-native interaction.

The prototype must be labeled as an **unofficial hackathon prototype** where appropriate. Do not imply Razorpay endorsement.

---

# 2. Research basis

Use current public Razorpay design sources as inspiration:

1. **RazorSense** — Razorpay's public design language for the AI era. Its public description emphasizes motion, context, emotion, the Razorpay glyph, and giving distinct feeling/purpose to states and interactions.
2. **Blade** — the open-source design system that powers Razorpay, with accessible cross-platform components, tokens and documented API decisions.

The agent must record current links/findings in `RESEARCH.md` before finalizing design-system implementation.

Do not invent an "official Razorpay font" or private brand token if it is not publicly verified.

---

# 3. Blade-first rule

When current compatibility permits, prefer the public `@razorpay/blade` design system for:

- components;
- typography;
- spacing;
- colors/tokens;
- accessibility primitives;
- forms;
- feedback states;
- charts if useful.

Before adding it:

- live-check current package version;
- check React/Next compatibility;
- read current installation docs;
- inspect license;
- update `VERSION_MANIFEST.md`;
- run build/a11y/test gates.

If Blade causes material incompatibility or unnecessary Phase-1 complexity, document the decision and use a small internal token layer instead.

---

# 4. Typography

Priority:

1. Fonts officially exposed by the current public Blade package, if Blade is used.
2. Otherwise `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.

Do **not** claim the fallback is Razorpay's official font.

Use:

- display: restrained, high-impact only;
- headings: 600–700;
- body: 400–500;
- labels/microcopy: 500–600;
- tabular numerals for money/metrics where possible.

Avoid tiny text. Minimum normal UI text target: 14px, with most body copy 15–16px.

---

# 5. Project fallback tokens

If Blade tokens are not used, these are **RazorMesh project tokens**, not claims about Razorpay's official palette.

```text
--rm-bg:            #F6F8FC
--rm-surface:       #FFFFFF
--rm-surface-2:     #EEF2F8
--rm-text:          #101828
--rm-text-muted:    #667085
--rm-border:        #D9E0EA
--rm-primary:       #2F5BFF
--rm-primary-hover: #2349D8
--rm-info:          #2563EB
--rm-success:       #15803D
--rm-warning:       #B45309
--rm-danger:        #B42318
--rm-focus:         #4F7CFF
```

Dark-mode fallback:

```text
--rm-bg:            #090D17
--rm-surface:       #111827
--rm-surface-2:     #182235
--rm-text:          #F8FAFC
--rm-text-muted:    #A9B4C6
--rm-border:        #29364A
```

Use semantic tokens, not raw colors scattered through components.

---

# 6. RazorSense-inspired state language

Public RazorSense messaging emphasizes that states/interactions should feel responsive and purposeful.

Translate that into restrained fintech UX:

## ALLOW
Feeling: confidence / completion.

- calm success state;
- checkmark/progress resolution;
- show exactly what was verified;
- never over-celebrate a financial action.

## CHALLENGE
Feeling: attentive pause.

- amber/caution;
- show the exact change/difference;
- primary CTA = review/approve;
- secondary CTA = cancel;
- no threatening language.

## BLOCK
Feeling: protective clarity.

- red/danger only where necessary;
- reason first, technical detail second;
- clearly state "No payment executed";
- show what violated authorization.

## THINKING / CHECKING
Feeling: active verification.

- visible progress through checks;
- skeleton/progress state;
- never fake an AI "thinking" animation if the backend is idle.

## PROVIDER UNKNOWN
Feeling: uncertainty without panic.

- state that outcome is being reconciled;
- do not expose a "Pay again" action that could duplicate the effect.

---

# 7. Interaction motion

Motion must communicate state, not decorate.

Preferred:

- 150–250 ms ordinary transitions;
- subtle progress transitions;
- no excessive bouncing/glows;
- no casino-like payment celebration;
- respect `prefers-reduced-motion`;
- animations must never hide security results.

---

# 8. Layout

Desktop prototype target:

- max content width around 1200–1440 px;
- 12-column or equivalent responsive grid;
- left navigation or compact top navigation;
- generous whitespace;
- cards with modest radius;
- clear hierarchy.

Mobile:

- all critical actions usable at 360 px width;
- no horizontal scrolling for core transaction state;
- security explanations collapse progressively.

---

# 9. Primary pages

## `/buyer`

Must show:

- current human authorization;
- products/search;
- proposed checkout;
- current amount;
- merchant/seller;
- RazorGuard result;
- execution state;
- mock-provider label.

## `/merchant`

Must show:

- synthetic catalog;
- merchant identity;
- product/price/subscription fields;
- ability in Security Lab/dev mode to mutate checkout state.

## `/security-lab`

Must show:

- scenario selector;
- before state;
- mutation/attack;
- RazorGuard checks;
- decision;
- provider-effect count;
- audit trace;
- expected vs actual result only after execution.

Use label:

> Synthetic Attack Simulation

Never imply attacking real Razorpay.

## `/audit`

Must show:

- chronological event timeline;
- reason codes;
- intent/checkout hash summary;
- ticket/nonce status;
- reservation/execution attempt state;
- audit-chain verification.

## `/`

Concise product overview and demo navigation.

---

# 10. Core components

Prefer reusable components such as:

- `TrustStateBadge`
- `DecisionCard`
- `IntentSummary`
- `CheckoutDiff`
- `RuleResultList`
- `ExecutionTimeline`
- `ReservationMeter`
- `TicketStatus`
- `EvidenceHash`
- `SecurityScenarioCard`
- `MetricCard`
- `MockProviderBanner`

---

# 11. Checkout diff

The most important UX component is an authorization diff.

Example:

```text
Authorized maximum     ₹5,000
Initial checkout       ₹4,799
Current checkout       ₹5,499
Difference             +₹700

Changed:
✓ product
✗ total
✗ shipping
✓ merchant
```

Do not make users infer why a challenge/block occurred.

---

# 12. Accessibility

Required:

- keyboard navigation;
- visible focus;
- semantic HTML;
- accessible names;
- sufficient contrast;
- color never the only state indicator;
- icons paired with text for critical states;
- reduced motion;
- screen-reader-friendly reason/status messages;
- test with automated accessibility tooling where practical.

---

# 13. Brand asset rule

- Do not download or redistribute proprietary font files.
- Do not invent/modify Razorpay logos.
- If an official logo is used for hackathon context, use only authorized public brand assets and follow published usage terms.
- Prefer "RazorMesh Trust" identity with textual note "Built for Razorpay Buildathon" rather than presenting the app as an official Razorpay product.

---

# 14. Design review gate

For every UI milestone verify:

- matches this design file;
- responsive;
- keyboard usable;
- critical states have text + visual distinction;
- no fake backend results;
- no hidden authorization logic in UI;
- no generic "AI dashboard" neon/sci-fi aesthetic;
- no excessive gradients;
- design still feels like a serious fintech product.
