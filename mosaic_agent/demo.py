from __future__ import annotations

import argparse
from pathlib import Path

from mosaic_agent.export import export_artifacts
from mosaic_agent.intake import MissingCriticalFieldsError
from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.loop import run_agent_loop
from mosaic_agent.models import ConceptPackage
from mosaic_agent.providers.base import ProviderConfigurationError, ProviderRuntimeError
from mosaic_agent.visual import generate_visual_artifacts


def run_demo(
    *,
    palette_path: str | Path,
    brief_path: str | Path,
    mode: str,
    allow_assumptions: bool,
    out_dir: str | Path,
) -> ConceptPackage:
    brief = load_brief(brief_path)
    palette = load_palette(palette_path)
    package = run_agent_loop(brief=brief, palette=palette, mode=mode, allow_assumptions=allow_assumptions)
    export_artifacts(package, out_dir)
    generate_visual_artifacts(package=package, brief=brief, palette=palette, out_dir=out_dir, mode=mode)
    return package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the mosaic design agent demo loop.")
    parser.add_argument("--palette", required=True, type=Path, help="Path to palette DB JSON.")
    parser.add_argument("--brief", required=True, type=Path, help="Path to project brief JSON.")
    parser.add_argument("--mode", default="stub", choices=["stub", "openai-image", "gemini-image"], help="Execution mode.")
    parser.add_argument("--allow-assumptions", action="store_true", help="Continue with explicit assumptions.")
    parser.add_argument("--out", required=True, type=Path, help="Output directory for artifacts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        package = run_demo(
            palette_path=args.palette,
            brief_path=args.brief,
            mode=args.mode,
            allow_assumptions=args.allow_assumptions,
            out_dir=args.out,
        )
    except MissingCriticalFieldsError as error:
        args.out.mkdir(parents=True, exist_ok=True)
        questions_md = "# Artist Questions\n\n" + "\n".join(f"- {question}" for question in error.questions) + "\n"
        (args.out / "artist_questions.md").write_text(questions_md, encoding="utf-8")
        parser.error(
            "critical fields are missing; rerun with --allow-assumptions to generate concepts, "
            f"or answer questions in {args.out / 'artist_questions.md'}"
        )
        return 2
    except ProviderConfigurationError as error:
        parser.exit(2, f"Provider configuration error: {error}\n")
    except ProviderRuntimeError as error:
        parser.exit(1, f"Provider runtime error: {error}\n")

    print(f"Exported {len(package.concepts)} concepts and visual contact sheet to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
