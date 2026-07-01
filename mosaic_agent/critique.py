from __future__ import annotations

from mosaic_agent.models import Critique, CritiqueScores, ProjectBrief


def build_stub_critique(concept_name: str, brief: ProjectBrief) -> Critique:
    if concept_name == "Desert Sunrise Welcome":
        return Critique(
            scores=CritiqueScores(
                palette_adherence=5,
                distance_readability=4,
                tile_buildability=4,
                text_survivability=4,
                style_fit=5,
                novelty=3,
            ),
            notes=[
                "Warm high-inventory tiles carry the large sky and desert regions without inventing colors.",
                "The sunrise arc gives a strong road-distance focal shape while leaving Yael room for handmade shard flow.",
            ],
            risks=[
                "Sunset gradients could become too smooth for broken tile if the palette is not grouped into broad bands.",
                "Hebrew lettering needs large cream/off-white strokes with dark shadow separation.",
            ],
        )

    if concept_name == "Path Into Community":
        return Critique(
            scores=CritiqueScores(
                palette_adherence=5,
                distance_readability=4,
                tile_buildability=5,
                text_survivability=3,
                style_fit=4,
                novelty=4,
            ),
            notes=[
                "The path-led composition turns the entrance stone into a welcoming directional gesture.",
                "Vegetation accents stay limited, so low-inventory and splintery greens do not dominate large fields.",
            ],
            risks=[
                "Community details must stay symbolic; small people, houses, or objects would not survive at entrance distance.",
                "Text can compete with the path unless its region is locked early.",
            ],
        )

    return Critique(
        scores=CritiqueScores(
            palette_adherence=5,
            distance_readability=5,
            tile_buildability=4,
            text_survivability=5,
            style_fit=4,
            novelty=4,
        ),
        notes=[
            "Typography becomes the main composition instead of an afterthought, improving public readability.",
            "Ribbon bands can follow the irregular stone face and absorb palette variation without needing a compiler.",
        ],
        risks=[
            "The concept may feel too graphic if dark outlines are overused.",
            "Letter geometry must be drawn by the artist, not trusted to an image model.",
        ],
    )
