"""Disagreement regression coverage for the internal human-labelling tool."""
import pandas as pd
import pytest

from tools.merge_internal_labels import main, reconcile_labels


@pytest.mark.parametrize("column,value", [("defect_type", "glare"), ("is_defect", "0"), ("severity", "2")])
def test_any_label_field_disagreement_requires_adjudication(tmp_path, column, value):
    first = pd.DataFrame([{"image_id": "sample", "annotator": "A", "defect_type": "blur",
                           "is_defect": "1", "severity": "1"}])
    second = first.copy().assign(annotator="B")
    second.loc[0, column] = value
    a, b, out, disagree = [tmp_path / f"{name}.csv" for name in ("a", "b", "merged", "disagreements")]
    first.to_csv(a, index=False)
    second.to_csv(b, index=False)
    assert main(["--a", str(a), "--b", str(b), "--out", str(out), "--disagree", str(disagree)]) == 1
    merged = pd.read_csv(out, dtype=str).fillna("")
    differences = pd.read_csv(disagree, dtype=str)
    assert merged.loc[0, "status"] == "NEEDS_ADJUDICATION"
    assert merged.loc[0, column] == ""
    assert len(differences) == 1
    assert differences.loc[0, f"{column}_A"] != differences.loc[0, f"{column}_B"]
    assert first.loc[0, column] != second.loc[0, column]


def test_complete_agreement_returns_success(tmp_path):
    source = pd.DataFrame([{"image_id": "sample", "annotator": "A", "defect_type": "none",
                            "severity": "0", "is_defect": "0"}])
    a, b, out, disagree = [tmp_path / f"{name}.csv" for name in ("a", "b", "merged", "disagreements")]
    source.to_csv(a, index=False)
    source.to_csv(b, index=False)
    assert main(["--a", str(a), "--b", str(b), "--out", str(out), "--disagree", str(disagree)]) == 0
    assert pd.read_csv(out).loc[0, "status"] == "agreed"
    assert pd.read_csv(disagree).empty


def test_blank_agreement_is_not_a_resolved_label():
    frame = pd.DataFrame({"defect_type_A": ["blur"], "defect_type_B": ["blur"],
                          "is_defect_A": [""], "is_defect_B": [""],
                          "severity_A": ["1"], "severity_B": ["1"]}, index=["sample"])
    merged, dis = reconcile_labels(frame)
    assert merged.loc["sample", "status"] == "NEEDS_ADJUDICATION"
    assert len(dis) == 1


def test_severity_cannot_be_compared_against_an_absent_column():
    frame = pd.DataFrame({"defect_type_A": ["none"], "defect_type_B": ["none"],
                          "is_defect_A": ["0"], "is_defect_B": ["0"], "severity_A": ["0"]})
    with pytest.raises(ValueError, match="both labelling files"):
        reconcile_labels(frame)


def test_legacy_files_without_severity_still_compare_required_fields():
    frame = pd.DataFrame({"defect_type_A": ["none"], "defect_type_B": ["none"],
                          "is_defect_A": ["0"], "is_defect_B": ["0"]})
    merged, dis = reconcile_labels(frame)
    assert merged.loc[0, "status"] == "agreed" and dis.empty
