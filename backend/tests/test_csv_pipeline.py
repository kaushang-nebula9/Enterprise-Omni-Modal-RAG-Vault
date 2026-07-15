import sys
import os
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.document_processor import extract_excel_schema
from app.services.rag_service import execute_excel_query
from unittest.mock import patch, MagicMock


def test_csv_comma_utf8():
    content = "name,age,city\nAlice,30,New York\nBob,25,Los Angeles\nCharlie,35,Chicago"
    with tempfile.NamedTemporaryFile(
        suffix=".csv", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        schema = extract_excel_schema(tmp_path)
        assert schema["columns"] == ["name", "age", "city"]
        assert schema["shape"] == {"rows": 3, "columns": 3}
        assert schema["dtypes"]["age"] in ("int64", "int32")
        assert len(schema["sample"]) == 3
        assert schema["sample"][0]["name"] == "Alice"
    finally:
        os.remove(tmp_path)


def test_csv_semicolon_latin1():
    # Semicolon-separated, latin-1 encoding
    content = "name;café_spent;city\nAlice;12.5;Montréal\nBob;8.0;Paris"
    with tempfile.NamedTemporaryFile(
        suffix=".csv", mode="w", encoding="latin-1", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        schema = extract_excel_schema(tmp_path)
        assert schema["columns"] == ["name", "café_spent", "city"]
        assert schema["shape"] == {"rows": 2, "columns": 3}
        assert schema["sample"][0]["city"] == "Montréal"
    finally:
        os.remove(tmp_path)


def test_csv_tab_utf8():
    content = "name\tage\tcity\nAlice\t30\tNew York"
    with tempfile.NamedTemporaryFile(
        suffix=".csv", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        schema = extract_excel_schema(tmp_path)
        assert schema["columns"] == ["name", "age", "city"]
        assert schema["shape"] == {"rows": 1, "columns": 3}
    finally:
        os.remove(tmp_path)


@patch("app.services.rag_service._get_anthropic_client")
def test_execute_excel_query_csv(mock_get_client):
    content = "name,age\nAlice,30\nBob,25"
    with tempfile.NamedTemporaryFile(
        suffix=".csv", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    # Mock Anthropic response
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(text="result = df[df['name'] == 'Alice']['age'].values[0]")
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    mock_get_client.return_value = mock_client

    try:
        schema = extract_excel_schema(tmp_path)
        res = execute_excel_query(tmp_path, schema, "How old is Alice?")
        assert res == "30"
    finally:
        os.remove(tmp_path)
