# Gold Review — Instructions

You are labeling whether the EVIDENCE supports the AUTHORIZATION CLAIM.

Orientation (fixed):
- PREMISE  = trusted evidence about the product/listing/seller.
- HYPOTHESIS = a statement about what the human authorized.

Labels:
- 1 entailment      evidence clearly supports the authorization holding;
- 2 neutral         evidence insufficient to decide;
- 3 contradiction   evidence proves the authorization does NOT hold.

Procedure:
1. Open `gold_review.html` in your browser (double-click; no server needed).
2. For each card read PREMISE then HYPOTHESIS, ignore the suggested label
   until you have decided, then press 1 / 2 / 3.
3. Use ← → to move around; progress bar fills as you go.
4. When finished (or anytime), press E to export `gold_decisions.json`.
5. Save that file next to this folder and tell the agent it exists.

Notes:
- The CSV's suggested_label column is machine-suggested ground truth used for
  cross-checking AFTER your pass; try not to anchor on it.
- Target: complete ALL rows. Partial exports are fine — rerun and continue.
