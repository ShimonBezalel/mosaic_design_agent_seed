---
name: mosaic-brief-intake
description: Use when turning a vague public mosaic idea into a structured design brief before ideation.
---

# Mosaic Brief Intake

## Purpose

Convert messy user/artist input into a structured project brief for mosaic ideation.

## Use when

- The user describes a mosaic/public-art project.
- The user provides references, palette constraints, canvas constraints, or artistic intent.
- The agent is tempted to generate concepts before understanding the task.

## Process

1. Extract known facts.
2. Identify critical unknowns.
3. Ask only the questions that block useful ideation.
4. Mark any assumptions explicitly.
5. Produce/update a `ProjectBrief` object.

## Critical unknowns

- actual canvas/stone dimensions;
- required text and language;
- expected viewing distance;
- must-include symbols;
- must-avoid elements;
- desired granularity;
- whether the desired output is sketch, moodboard, render, or execution map.

## Output format

Return:

```json
{
  "known_facts": [],
  "critical_unknowns": [],
  "questions": [],
  "assumptions": [],
  "project_brief_patch": {}
}
```

## Style

Ask practical studio questions. Do not ask broad philosophical questions unless the emotional/artistic direction is genuinely missing.
