from __future__ import annotations

import argparse
from pathlib import Path

from mosaic_agent.export import export_artifacts
from mosaic_agent.intake import MissingCriticalFieldsError
from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.loop import run_agent_loop
from mosaic_agent.models import ConceptPackage
from mosaic_agent.providers.base import ProviderConfigurationError, ProviderRuntimeError
from mosaic_agent.reference_images import ReferenceImageError
from mosaic_agent.visual import generate_visual_artifacts


def run_demo(
    *,
    palette_path: str | Path,
    brief_path: str | Path,
    mode: str | None = None,
    ideation_mode: str = "stub",
    image_mode: str = "stub",
    allow_assumptions: bool = False,
    out_dir: str | Path,
    concept_limit: int = 3,
    variants_per_concept: int = 2,
    image_size: str = "1536x1024",
    image_quality: str = "low",
    image_model: str | None = None,
) -> ConceptPackage:
    if mode is not None:
        ideation_mode = "stub"
        image_mode = mode
    brief = load_brief(brief_path)
    palette = load_palette(palette_path)
    package = run_agent_loop(
        brief=brief,
        palette=palette,
        ideation_mode=ideation_mode,
        image_mode=image_mode,
        allow_assumptions=allow_assumptions,
        concept_limit=concept_limit,
    )
    export_artifacts(package, out_dir)
    generate_visual_artifacts(
        package=package,
        brief=brief,
        palette=palette,
        out_dir=out_dir,
        ideation_mode=ideation_mode,
        image_mode=image_mode,
        variants_per_concept=variants_per_concept,
        image_size=image_size,
        image_quality=image_quality,
        image_model=image_model,
    )
    return package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the mosaic design agent demo loop.")
    parser.add_argument("--palette", required=True, type=Path, help="Path to palette DB JSON.")
    parser.add_argument("--brief", required=True, type=Path, help="Path to project brief JSON.")
    parser.add_argument(
        "--mode",
        choices=["stub", "openai-image", "openai-responses-image", "gemini-image"],
        help="Legacy execution mode. Maps to --ideation-mode stub and the selected --image-mode.",
    )
    parser.add_argument("--ideation-mode", default="stub", choices=["stub", "openai"], help="Concept ideation mode.")
    parser.add_argument(
        "--image-mode",
        default="stub",
        choices=["stub", "openai-image", "openai-responses-image", "gemini-image"],
        help="Image generation mode.",
    )
    parser.add_argument("--allow-assumptions", action="store_true", help="Continue with explicit assumptions.")
    parser.add_argument("--concept-limit", default=3, type=int, help="Maximum number of concepts to generate.")
    parser.add_argument("--variants-per-concept", default=2, type=int, help="Image variants per concept.")
    parser.add_argument("--image-size", default="1536x1024", help="Requested image size.")
    parser.add_argument("--image-quality", default="low", choices=["low", "medium", "high", "auto"], help="Image quality.")
    parser.add_argument("--image-model", default=None, help="Provider model override.")
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
            ideation_mode=args.ideation_mode,
            image_mode=args.image_mode,
            allow_assumptions=args.allow_assumptions,
            out_dir=args.out,
            concept_limit=args.concept_limit,
            variants_per_concept=args.variants_per_concept,
            image_size=args.image_size,
            image_quality=args.image_quality,
            image_model=args.image_model,
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
    except ReferenceImageError as error:
        parser.exit(2, f"Reference image error: {error}\n")

    print(f"Exported {len(package.concepts)} concepts and visual contact sheet to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
