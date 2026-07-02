# Current Status

The repo now includes:

- typed brief, palette, concept, visual manifest, and interactive session models;
- deterministic and OpenAI concept ideation;
- stub, OpenAI Images, OpenAI Responses image, Gemini, and OpenAI masked-edit adapters;
- a local Gradio workbench at `python -m mosaic_workbench.app`;
- mask upload/drawing, normalization, alpha handling, and overlay preview;
- concept selection, masked variant generation, and portable session export;
- deterministic CIEDE2000 palette matching constrained to selected studio tile IDs;
- mask-aware SLIC segmentation with deterministic grid fallback;
- connected-region cleanup, tiny-region merging, stable IDs, area accounting, and signatures;
- a Gradio **Compile to Tile Map** tab that works from upload, latest variant, or base canvas;
- flat maps, numbered regions, boundary overlays, SVG, CSV, QA JSON, HTML, and ZIP export;
- a checked-in offline compile demo and exhaustive synthetic compiler tests;
- offline stub integration tests and opt-in paid provider canaries.

The center of gravity is now finalized image to deterministic studio-palette planning map. Optional ideation remains available. Outputs still require artist review and are not construction-ready mosaic plans.
