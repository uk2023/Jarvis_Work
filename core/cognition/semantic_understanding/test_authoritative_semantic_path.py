"""Regression checks for the single authoritative semantic path."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRAIN = ROOT / "core" / "orchestration" / "brain.py"


def test_brain_has_no_runtime_legacy_fact_extraction_call() -> None:
    source = BRAIN.read_text(encoding="utf-8")
    assert "self._extract_fact(" not in source
    print("PASS: Brain does not invoke the legacy post-response fact extractor")


def test_semantic_boundary_owns_learning_intake() -> None:
    boundary = Path(__file__).resolve().parent / "learning_boundary.py"
    source = boundary.read_text(encoding="utf-8")
    assert "class SemanticLearningBoundary" in source
    assert "LearningCoordinator" in source
    print("PASS: Semantic Understanding owns the fallback -> learning boundary")


def main() -> None:
    test_brain_has_no_runtime_legacy_fact_extraction_call()
    test_semantic_boundary_owns_learning_intake()
    print("PASS: single authoritative semantic path cleanup validated")


if __name__ == "__main__":
    main()
