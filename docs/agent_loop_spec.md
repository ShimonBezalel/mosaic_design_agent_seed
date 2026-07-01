# Agent Loop Spec

## Loop policy

The agent is allowed to produce ideation results only after it has:

1. parsed the brief;
2. loaded the palette DB;
3. checked for missing critical constraints;
4. either asked clarifying questions or explicitly marked assumptions.

## Critical fields

The agent should ask follow-up questions when these are missing:

- project name / location;
- canvas/stone shape and dimensions;
- required text, if any;
- viewing distance;
- installation mood: ceremonial, playful, desert, modern, local, etc.;
- must-include symbols;
- must-avoid symbols/colors;
- desired granularity;
- whether generated images should be realistic mockups, flat sketches, or both.

## Soft fields

The agent may assume these temporarily:

- exact tile inventory quantities;
- lighting conditions;
- preferred output format;
- number of concept variants;
- language of labels.

## Agent loop pseudocode

```text
run_mosaic_design_agent(brief, palette, mode):
    state = parse_inputs(brief, palette)
    missing = check_missing_critical_fields(state)

    if missing:
        return QuestionSet(missing)

    palette_summary = summarize_palette(palette)
    concepts = generate_concepts(brief, palette_summary, n=3)

    for concept in concepts:
        concept.palette_subset = choose_palette_subset(concept, palette)
        concept.image_prompts = build_image_prompts(concept, brief)

        if mode.real_images:
            concept.image_results = image_provider.generate(concept.image_prompts)
        else:
            concept.image_results = stub_image_results(concept.image_prompts)

        concept.critique = critique_concept(concept, brief, palette)

    package = rank_and_export(concepts)
    return package
```

## First conversation behavior

The agent should be comfortable saying:

> I can produce concept directions now, but these assumptions are active: [...].

For tomorrow, this is good. It allows Yael to react quickly.

## Concept diversity policy

Do not return three versions of the same idea. Return directions that differ in composition:

1. symbolic/ceremonial;
2. landscape/local nature;
3. community/children/entrance-welcome;
4. abstract color-flow;
5. typography-led.

Pick three based on the brief.

## Critique rubric

Each concept gets scores 1–5:

- palette adherence;
- distance readability;
- tile buildability;
- text survivability;
- Yael-style fit;
- emotional fit;
- novelty;
- risk.

High risk is not bad. It means it needs discussion.
