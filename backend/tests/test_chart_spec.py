import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.utils import extract_chart_spec


def test_extract_chart_spec_success():
    llm_response = (
        "Here is the data comparing quarterly sales:\n"
        "Quarter 1 sales were 10k, Quarter 2 was 15k.\n"
        'CHART_SPEC:{"chart_type":"bar","title":"Quarterly Sales","x_key":"quarter","y_keys":["sales"],"data":[{"quarter":"Q1","sales":10000},{"quarter":"Q2","sales":15000}]}'
    )
    cleaned, spec = extract_chart_spec(llm_response)

    assert spec is not None
    assert spec["chart_type"] == "bar"
    assert spec["title"] == "Quarterly Sales"
    assert spec["x_key"] == "quarter"
    assert spec["y_keys"] == ["sales"]
    assert len(spec["data"]) == 2
    assert spec["data"][0]["quarter"] == "Q1"
    assert spec["data"][0]["sales"] == 10000

    # Assert CHART_SPEC line is stripped and trailing/leading whitespace is cleaned
    assert "CHART_SPEC:" not in cleaned
    assert (
        cleaned
        == "Here is the data comparing quarterly sales:\nQuarter 1 sales were 10k, Quarter 2 was 15k."
    )


def test_extract_chart_spec_no_spec():
    llm_response = (
        "Here is the data comparing quarterly sales:\n"
        "Quarter 1 sales were 10k, Quarter 2 was 15k."
    )
    cleaned, spec = extract_chart_spec(llm_response)

    assert spec is None
    assert cleaned == llm_response


def test_extract_chart_spec_invalid_json():
    llm_response = (
        "Here is the data comparing quarterly sales:\n"
        "Quarter 1 sales were 10k, Quarter 2 was 15k.\n"
        "CHART_SPEC:{invalid_json}"
    )
    cleaned, spec = extract_chart_spec(llm_response)

    assert spec is None
    assert cleaned == llm_response


def test_extract_chart_spec_empty_string():
    cleaned, spec = extract_chart_spec("")
    assert spec is None
    assert cleaned == ""
