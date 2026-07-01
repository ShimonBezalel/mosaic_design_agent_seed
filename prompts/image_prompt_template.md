# Image Prompt Template

Use this template to generate provider-specific prompts.

## OpenAI / GPT Image prompt

Create a flat concept rendering for a handmade broken-ceramic-tile mosaic public artwork on a large natural stone at a town entrance.

Project: {project_name}
Location: {location}
Mood: {desired_mood}
Required Hebrew text: {required_text}
Concept: {concept_name}
Composition: {composition}
Palette constraint: use only these approximate tile colors: {palette_hex_list_with_names}
Mosaic grammar: irregular broken ceramic pieces, visible grout, larger pieces in background, smaller controlled pieces around text and focal symbols, hand-made not pixelated.
Important: text must be large, simple, high contrast, and readable from distance. Avoid tiny details.
Output style: flat proposal render, not photorealistic, suitable for artist discussion.

## Gemini / Nano Banana prompt

Edit/generate a concept board for a handmade broken-tile mosaic mural on an irregular natural stone. Use the provided reference style and these exact palette colors: {palette_hex_list_with_names}. Keep the Hebrew text readable and treat it as large mosaic-letter geometry. Make the image useful as an ideation sketch, not as final execution art.

## Negative prompt / avoid-list

No pixel mosaic, no tiny photorealistic details, no colors outside palette, no illegible Hebrew, no over-smooth digital gradients, no stock-logo feeling, no fake perfect tile grid.
