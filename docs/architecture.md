# Architecture Sketch

## Runtime architecture

```text
User / Yael
   |
   v
Design Orchestrator Agent
   |-- asks missing questions
   |-- calls tools
   |-- hands off to specialist agents/tools when needed
   |
   +--> Palette Lookup Tool
   +--> Brief Completeness Tool
   +--> Concept Generator Tool/Agent
   +--> Prompt Builder Tool/Agent
   +--> Visual Ideation Provider Adapter
   |       |-- Stub provider
   |       |-- OpenAI image provider
   |       |-- Gemini Nano Banana provider
   |
   +--> Mosaic Critic Tool/Agent
   +--> Artifact Exporter
```

## Specialist responsibilities

### Design Orchestrator
Owns the user conversation and final package. It decides whether to ask more questions, generate concepts, call image tools, or critique.

### Brief Intake
Turns free text into structured fields. Flags unknowns.

### Palette Grounding
Filters and summarizes tile colors. Enforces palette constraints. Rejects concepts that require missing colors.

### Ideation
Produces multiple directions. Each direction should be compositionally distinct, not just prompt variations.

### Prompt Builder
Turns concept packages into tool-specific prompts. This keeps prompt-writing separate from artistic reasoning.

### Visual Provider
Generates or simulates images. In stub mode it returns deterministic placeholder metadata instead of calling APIs.

### Mosaic Critic
Evaluates distance readability, text survivability, palette adherence, granularity, field buildability, and Yael-style fit.

### Exporter
Writes JSON and Markdown artifacts for review.

## Data flow

1. Load `ProjectBrief`.
2. Load `PaletteDB`.
3. Run completeness check.
4. If critical fields are missing, ask questions.
5. Select candidate palette subset.
6. Generate 3 concept directions.
7. For each concept, generate image-tool prompts.
8. Optionally call image provider.
9. Critique each concept.
10. Export `ConceptPackage`.

## State model

The agent run should preserve:

- brief fields;
- answered questions;
- palette subset;
- generated concepts;
- tool calls and tool responses;
- critique results;
- revision notes.

## Tool approval policy

Always allow safe local reads/writes under the project directory.

Require explicit user approval for:

- calling paid external image APIs;
- using web search;
- sending/sharing results externally;
- deleting files;
- changing palette DB records.

## Provider abstraction

Define an image provider interface independent of the agent SDK:

```python
class ImageProvider(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...
```

This lets the same agent call:

- stub mode for tests;
- OpenAI image API;
- Gemini/Nano Banana API;
- future local diffusion/ComfyUI pipeline.
