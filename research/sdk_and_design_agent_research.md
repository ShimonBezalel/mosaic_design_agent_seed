# SDK and Design-Agent Research Notes

Research date: 2026-07-01.

## Superpowers brainstorming pattern

The useful part of `superpowers:brainstorming` is procedural discipline: start with context, ask clarifying questions, compare approaches, produce a design/spec, review it, and only then implement. For this project that means Codex should not jump directly into image generation. It should first implement a question-driven intake and structured output loop.

Source: https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md

## OpenAI Agents SDK

OpenAI's Agents SDK defines an agent as an LLM configured with instructions, tools, and optional runtime behavior such as handoffs, guardrails, and structured outputs. The SDK also supports tracing, with traces covering LLM generations, tool calls, handoffs, guardrails, and custom events.

Relevant docs:

- https://openai.github.io/openai-agents-python/agents/
- https://openai.github.io/openai-agents-python/tools/
- https://openai.github.io/openai-agents-python/handoffs/
- https://openai.github.io/openai-agents-python/tracing/
- https://developers.openai.com/api/docs/guides/agents

Implication for this project:

- Good first runtime for a product agent loop.
- Strong fit for typed outputs, tool wrappers, guardrails, and trace review.
- The real image APIs can be hidden behind custom tools, so local stub mode remains easy.

## OpenAI image generation

OpenAI image generation can run either through the Image API or as an image-generation tool in the Responses API. The Responses API path is better for conversational, iterative image workflows; the Image API is simpler for one-off generation/edit requests.

Relevant docs:

- https://developers.openai.com/api/docs/guides/image-generation
- https://developers.openai.com/api/docs/guides/tools-image-generation

Implication:

- For the first real loop, use function tools returning structured image-prompt artifacts before actually generating images.
- Add image generation only after the stub loop is stable.

## Anthropic Claude Agent SDK

Anthropic's Agent SDK gives programmable access to the same agent loop and context management used by Claude Code, in Python and TypeScript. It is good for agents that read files, run commands, search the web, edit code, and use MCP. Anthropic also has an explicit Skills system for reusable instruction/script/resource bundles.

Relevant docs:

- https://docs.anthropic.com/en/docs/claude-code/sdk
- https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-python
- https://docs.anthropic.com/en/docs/claude-code/sub-agents
- https://docs.anthropic.com/en/docs/claude-code/skills
- https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- https://www.anthropic.com/engineering/code-execution-with-mcp

Implication:

- Excellent for a Claude Code implementation harness and future subagent system.
- Slightly less direct for the product runtime if we want a clean Python app with custom image provider adapters and traceable typed outputs.
- Keep all prompts/skills portable so either SDK can consume them.

## Gemini / Nano Banana

Google's current Gemini image-generation docs describe Nano Banana as Gemini's native image generation capabilities, supporting conversational generation and editing from text and images. Gemini API docs also expose structured outputs and function calling, which are relevant if using Gemini as either a generator or an agentic backend.

Relevant docs:

- https://ai.google.dev/gemini-api/docs/image-generation
- https://ai.google.dev/gemini-api/docs

Implication:

- Treat Nano Banana as an image provider, not as the whole agent framework.
- The first implementation should use a `GeminiNanoBananaProvider` interface but not require credentials in smoke tests.

## What the market seems to be doing

Creative/design-agent products increasingly package moodboards, brand/palette constraints, image generation, natural-language iteration, and exportable design artifacts into one conversational workflow. The strongest pattern is not a single prompt -> image. It is: intake -> constraints -> references -> generate variants -> critique -> revise -> export.

Relevant public examples/research:

- Google's Mixboard is positioned as an AI moodboard/design canvas built around generative imagery and natural-language edits.
- Recent agentic image-generation research separates visual understanding, tool invocation, generation, judgment, and refinement.
- Code-driven visual generation research uses intermediate artifacts such as SVG/HTML/Three.js to regain controllability before using an image model for texture or polish.

Useful references:

- https://arxiv.org/abs/2601.18543
- https://arxiv.org/abs/2605.30248
- https://arxiv.org/abs/2501.04163
- https://arxiv.org/abs/2509.02000

Implication:

- The mosaic agent should produce intermediate, inspectable artifacts, not only images.
- The palette DB should be a hard constraint.
- The agent should separate ideation from executability.

## Recommendation

Build tonight on OpenAI Agents SDK, with provider adapters for image tools and a portable skills/prompts layer. Structure the first version around repeatable tests, not around the prettiest image.
