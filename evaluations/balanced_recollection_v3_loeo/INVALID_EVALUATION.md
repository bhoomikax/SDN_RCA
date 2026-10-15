# Invalid evaluation record

This directory was produced on 2026-10-15 by a wrapper that recorded the v3
candidate hash but invoked an evaluator function whose definition-time default
argument still pointed to the milestone's 18-experiment dataset. The generated
split file contains 18 held-out experiments and does not include logical IDs
20–25. Therefore these scores are **not results for the v3 candidate** and must
not be cited as such. The artifacts are preserved for auditability. A corrected,
generalized evaluator and a separate output directory are used for v3.
