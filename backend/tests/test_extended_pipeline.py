import io
import os
import tempfile
import pytest
import pandas as pd
from fastapi import UploadFile, HTTPException

from app.models.enums import FileType
from app.services.document_processor import (
    load_dataframe,
    validate_upload_file,
    extract_excel_schema,
)
from app.services.rag_service import execute_excel_query
from unittest.mock import patch


def test_validate_upload_file_valid_pdf():
    file_bytes = b"%PDF-1.4 \n%..."
    upload_file = UploadFile(filename="test.pdf", file=io.BytesIO(file_bytes))
    file_type = validate_upload_file(upload_file)
    assert file_type == FileType.pdf


def test_validate_upload_file_invalid_mismatch():
    file_bytes = b"%PDF-1.4 \n%..."
    upload_file = UploadFile(filename="test.xlsx", file=io.BytesIO(file_bytes))
    with pytest.raises(HTTPException) as excinfo:
        validate_upload_file(upload_file)
    assert excinfo.value.status_code == 400
    assert "does not match detected MIME type" in excinfo.value.detail


def test_validate_upload_file_unsupported_ext():
    file_bytes = b"random content"
    upload_file = UploadFile(
        filename="test.random_ext_123", file=io.BytesIO(file_bytes)
    )
    with pytest.raises(HTTPException) as excinfo:
        validate_upload_file(upload_file)
    assert excinfo.value.status_code == 400
    assert "Unsupported file extension" in excinfo.value.detail


def test_validate_upload_file_tsv_plain_text():
    file_bytes = b"col1\tcol2\nval1\tval2"
    upload_file = UploadFile(filename="test.tsv", file=io.BytesIO(file_bytes))
    file_type = validate_upload_file(upload_file)
    assert file_type == FileType.tsv


def test_load_dataframe_tsv():
    content = "col1\tcol2\nval1\tval2"
    with tempfile.NamedTemporaryFile(
        suffix=".tsv", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        df = load_dataframe(tmp_path, FileType.tsv)
        assert list(df.columns) == ["col1", "col2"]
        assert df.shape == (1, 2)
        assert df.iloc[0]["col1"] == "val1"
    finally:
        os.remove(tmp_path)


def test_extract_excel_schema_tsv():
    content = "col1\tcol2\nval1\tval2"
    with tempfile.NamedTemporaryFile(
        suffix=".tsv", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        schema = extract_excel_schema(tmp_path, FileType.tsv)
        assert schema["columns"] == ["col1", "col2"]
        assert schema["shape"] == {"rows": 1, "columns": 2}
        assert schema["sample"][0]["col1"] == "val1"
    finally:
        os.remove(tmp_path)


def test_load_dataframe_ods():
    df_src = pd.DataFrame({"col1": ["val1"], "col2": [2]})
    with tempfile.NamedTemporaryFile(suffix=".ods", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        df_src.to_excel(tmp_path, engine="odf", index=False)
        df_read = load_dataframe(tmp_path, FileType.ods)
        assert list(df_read.columns) == ["col1", "col2"]
        assert df_read.shape == (1, 2)
        assert df_read.iloc[0]["col1"] == "val1"
    finally:
        os.remove(tmp_path)


def test_load_dataframe_xlsm():
    df_src = pd.DataFrame({"col1": ["val1"], "col2": [3]})
    with tempfile.NamedTemporaryFile(suffix=".xlsm", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        df_src.to_excel(tmp_path, engine="openpyxl", index=False)
        df_read = load_dataframe(tmp_path, FileType.xlsm)
        assert list(df_read.columns) == ["col1", "col2"]
        assert df_read.shape == (1, 2)
        assert df_read.iloc[0]["col1"] == "val1"
    finally:
        os.remove(tmp_path)


def test_validate_upload_file_legacy_xls():
    from unittest.mock import patch

    file_bytes = b"fake compound document bytes"
    upload_file = UploadFile(filename="test.xls", file=io.BytesIO(file_bytes))
    with patch("magic.from_buffer", return_value="application/CDFV2"):
        file_type = validate_upload_file(upload_file)
        assert file_type == FileType.xls


@patch("app.services.rag_service._get_anthropic_client")
def test_execute_excel_query_tsv(mock_get_client):
    from unittest.mock import MagicMock

    content = "name\tage\nAlice\t30\nBob\t25"
    with tempfile.NamedTemporaryFile(
        suffix=".tsv", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(text="result = df[df['name'] == 'Alice']['age'].values[0]")
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    mock_get_client.return_value = mock_client

    try:
        schema = extract_excel_schema(tmp_path, FileType.tsv)
        res = execute_excel_query(tmp_path, schema, "How old is Alice?", FileType.tsv)
        assert str(res) == "30"
    finally:
        os.remove(tmp_path)


def test_validate_upload_file_xlsb_as_openxml():
    from unittest.mock import patch

    file_bytes = b"fake xlsb openxml bytes"
    upload_file = UploadFile(filename="test.xlsb", file=io.BytesIO(file_bytes))
    with patch(
        "magic.from_buffer",
        return_value="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        file_type = validate_upload_file(upload_file)
        assert file_type == FileType.xlsb
