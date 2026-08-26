"""P3-M28/M29 core: label maps pinned to HF cards + metric math (no torch)."""

import pytest

from razormesh_api.nli_eval import (
    MODEL_LABEL_MAPS,
    argmax_to_project_label,
    compute_metrics,
    normalize_label,
)


def test_label_maps_match_official_model_cards() -> None:
    # R-020: MoritzLaurer card example order entailment/neutral/contradiction
    assert MODEL_LABEL_MAPS["MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"] == {
        0: "entailment",
        1: "neutral",
        2: "contradiction",
    }
    # cross-encoder card: contradiction/entailment/neutral (DIFFERENT ORDER!)
    assert MODEL_LABEL_MAPS["cross-encoder/nli-deberta-v3-base"] == {
        0: "contradiction",
        1: "entailment",
        2: "neutral",
    }


def test_argmax_normalization_differs_per_model() -> None:
    # index 1 means NEUTRAL for A but ENTAILMENT for B
    assert (
        argmax_to_project_label(1, model_key="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
        == "neutral"
    )
    assert argmax_to_project_label(1, model_key="cross-encoder/nli-deberta-v3-base") == "entailment"


def test_normalize_label_accepts_case_variants() -> None:
    assert normalize_label("Contradiction") == "contradiction"
    assert normalize_label("ENTAILMENT") == "entailment"
    with pytest.raises(ValueError):
        normalize_label("maybe")


def test_metrics_perfect_and_confused() -> None:
    gold = ["entailment", "entailment", "contradiction", "neutral"]
    pred = ["entailment", "neutral", "contradiction", "neutral"]
    m = compute_metrics(gold, pred)
    assert m.n == 4 and abs(m.accuracy - 0.75) < 1e-9
    ent = m.per_class["entailment"]
    assert ent.precision == pytest.approx(1.0)
    assert ent.recall == pytest.approx(0.5)
    assert m.per_class["contradiction"].f1 == 1.0
    assert 0 < m.macro_f1 < 1


def test_confusion_matrix_shape() -> None:
    m = compute_metrics(
        ["entailment", "neutral", "contradiction"] * 2,
        ["entailment", "entailment", "contradiction"] * 2,
    )
    assert set(m.confusion) == {"entailment", "neutral", "contradiction"}
    assert sum(sum(r.values()) for r in m.confusion.values()) == 6
