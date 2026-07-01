# Phase 3 — Image Providers

## Goal

Add image provider adapters without coupling them to the agent logic.

## Tasks

- Define `ImageGenerationRequest` and `ImageGenerationResult`.
- Implement `StubImageProvider`.
- Add placeholder classes for OpenAI and Gemini/Nano Banana with explicit env var checks.
- Add one integration test skipped unless env vars exist.

## Acceptance

- Provider selection works.
- Missing API key fails clearly.
- Stub provider remains default.
