"""Retired prototype pipeline; it must not bypass QA Engine authorization."""

class QAPipeline:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Prototype pipeline retired. Enroll a project and use qa_engine.Engine; see README.md.")
