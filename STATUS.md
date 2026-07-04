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
- exposed organic/balanced/regular SLIC compactness and physical color-area cleanup;
- connected-region cleanup, tiny-region merging, stable IDs, area accounting, and signatures;
- full-image and mask-bbox physical millimeter scale;
- deterministic edge-tangent flow with physical PCA fallback;
- deterministic physical seed generation and region-contained anisotropic tessera assignment;
- a Gradio **Compile to Tile Map** tab that works from upload, latest variant, or base canvas;
- separate color-area and tessera/shard controls and previews;
- flat maps, numbered regions, tessera maps, boundary overlays, SVG, CSV, QA JSON, HTML, and ZIP export;
- a checked-in offline compile demo and exhaustive synthetic compiler tests;
- offline stub integration tests and opt-in paid provider canaries.

The center of gravity is now finalized image to deterministic studio-palette color regions, followed by optional physically scaled tessera planning. Optional ideation remains available. Outputs still require artist review and are not construction-ready mosaic plans.
