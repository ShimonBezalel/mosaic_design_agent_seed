# Data Contracts

## PaletteDB

Text-only list of tile colors and material notes.

Minimum:

- `tile_id`
- `name`
- `hex`
- `inventory_level`

Recommended:

- `surface`
- `material`
- `break_profile`
- `preferred_uses`
- `avoid_uses`
- `notes`

## ProjectBrief

The structured input describing the public-art task.

Minimum:

- project name;
- location;
- free-text intent;
- required text;
- desired mood;
- canvas information;
- granularity preference;
- reference image paths.

## ConceptPackage

The exported output of a run.

Contains:

- run metadata;
- assumptions;
- questions;
- palette summary;
- concept directions;
- prompts;
- critiques;
- recommended next step.

## Why JSON first

JSON/Pydantic contracts make testing easier and keep the agent honest. Markdown is for people; JSON is for regression checks.
