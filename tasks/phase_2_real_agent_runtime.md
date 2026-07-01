# Phase 2 — Real Agent Runtime

## Goal

Add OpenAI Agents SDK orchestration while keeping stub mode intact.

## Tasks

- Add runtime adapter.
- Add function tools around palette lookup, intake, ideation, critique, export.
- Add structured output validation.
- Add tracing/logging.
- Keep all external calls opt-in.

## Acceptance

- Stub tests still pass.
- Real runtime can produce a valid `ConceptPackage` with stub image provider.
