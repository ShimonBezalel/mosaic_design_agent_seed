from __future__ import annotations

from mosaic_agent.models import ProjectBrief


class MissingCriticalFieldsError(RuntimeError):
    def __init__(self, questions: list[str]) -> None:
        self.questions = questions
        super().__init__("critical brief fields are missing")


def check_missing_critical_fields(brief: ProjectBrief) -> list[str]:
    questions: list[str] = []

    if brief.canvas.width_cm is None or brief.canvas.height_cm is None:
        questions.append("What are the stone face dimensions in centimeters, especially width and height?")
    if not brief.required_text:
        questions.append("Should the mosaic include required text, and if so what exact wording and language?")
    if brief.viewing_distance_m is None:
        questions.append("From what distance should the main text and focal symbol be readable?")
    if not brief.desired_mood:
        questions.append("Which mood should lead the design: ceremonial, playful, desert, modern, local, or another direction?")
    if not brief.must_include:
        questions.append("Which symbols, objects, or local references must appear in the design?")
    if not brief.must_avoid:
        questions.append("Are there symbols, colors, or visual tropes the design must avoid?")
    if brief.granularity == "unknown":
        questions.append("What tile granularity should dominate: coarse, medium, fine, or mixed?")
    if "image_renders" not in brief.desired_outputs:
        questions.append("For image generation later, should the target visual be a realistic stone mockup, a flat sketch, or both?")

    return questions


def assumptions_for_missing_fields(questions: list[str]) -> list[str]:
    assumptions: list[str] = []
    for question in questions:
        if "stone face dimensions" in question:
            assumptions.append("Stone face dimensions are not locked; concepts keep layouts broad and scalable.")
        elif "required text" in question:
            assumptions.append("No mandatory lettering is assumed until the artist confirms exact wording.")
        elif "distance" in question:
            assumptions.append("Viewing distance is assumed to be medium-range public entrance viewing.")
        elif "mood" in question:
            assumptions.append("Mood is assumed to be warm, local, and welcoming.")
        elif "must appear" in question:
            assumptions.append("Must-include symbols are treated as flexible until confirmed.")
        elif "must avoid" in question:
            assumptions.append("Avoid-list is limited to the current brief notes.")
        elif "granularity" in question:
            assumptions.append("Granularity is assumed mixed, with coarse public-readable regions and finer accents.")
        elif "image generation" in question:
            assumptions.append("Image prompts are written so they can support both realistic mockups and flat sketches.")
    return assumptions
