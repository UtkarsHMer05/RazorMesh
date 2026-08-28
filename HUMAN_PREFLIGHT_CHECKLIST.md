# Human Preflight Checklist

1. Do not perform the final Phase-4 Razorpay payment yet.
2. Keep the old `artifacts/models/incoming/phase3-finetuned/` checkpoint untouched as a baseline.
3. Keep the current UI as approved.
4. Ensure roughly 20–30 GB comfortable free disk space for datasets/caches/checkpoints.
5. Do not manually download datasets yet; the agent first performs source/license gates.
6. Be prepared for one human review gate later.
7. If local training is inadequate, allow a reproducible Colab bundle/handoff rather than ad-hoc training.
8. Do not paste secrets into prompts.
9. Perform exactly one final Razorpay Test payment only after the agent reaches the final human gate.
