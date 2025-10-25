import pandas as pd
import pytest
from pathlib import Path
from datetime import date, datetime
from firefly_csv_converter.convert_rico_cc import parse_input

def _write_excel(path: Path, rows):
    # Write raw rows to an Excel file without a header (so header detection can run)
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False, header=False)

def test_parse_input_parses_and_formats(tmp_path):
    file_path = tmp_path / "rico.xlsx"

    # Build a sheet where header is on row index 2 and starts at column 1
    rows = [
        [None, None, None, None, None, None],
        [None, None, None, None, None, None],
        [None, "Movimentação", "Liquidação", "Lançamento", "Valor", "Saldo"],
        [None, pd.Timestamp("2020-01-01 12:34:56"), pd.Timestamp("2020-01-02 00:00:00"), "Desc A", 1234.56, 2000.0],
        [None, pd.Timestamp("2020-02-03"), pd.Timestamp("2020-02-04"), "Desc B", 789.0, None],
    ]
    _write_excel(file_path, rows)

    df = parse_input(file_path)

    # Columns should be exactly the expected ones in the expected order
    assert list(df.columns) == ["Movimentação", "Liquidação", "Lançamento", "Valor", "Saldo"]

    # Two data rows
    assert df.shape[0] == 2

    # Date columns should be converted to datetime.date
    assert isinstance(df.iloc[0]["Movimentação"], date)
    assert isinstance(df.iloc[0]["Liquidação"], date)
    assert df.iloc[0]["Movimentação"] == date(2020, 1, 1)
    assert df.iloc[0]["Liquidação"] == date(2020, 1, 2)

    # Numeric columns should be formatted with comma decimal separator
    assert df.iloc[0]["Valor"] == "1234,56"
    assert df.iloc[0]["Saldo"] == "2000,00"
    assert df.iloc[1]["Valor"] == "789,00"
    # Missing numeric becomes empty string
    assert df.iloc[1]["Saldo"] == ""

def test_parse_input_truncates_after_empty_row(tmp_path):
    file_path = tmp_path / "rico_truncate.xlsx"

    rows = [
        [None, None, None, None],
        ["", "Movimentação", "Liquidação", "Valor"],
        [None, pd.Timestamp("2021-01-01"), pd.Timestamp("2021-01-02"), 10.0],
        [None, None, None, None],  # empty row that should cause truncation
        [None, pd.Timestamp("2022-01-01"), pd.Timestamp("2022-01-02"), 20.0],
    ]
    _write_excel(file_path, rows)

    df = parse_input(file_path)

    # Only the row before the first fully empty row should remain
    assert df.shape[0] == 1
    assert df.iloc[0]["Valor"] == "10,00"

def test_parse_input_raises_when_header_missing(tmp_path):
    file_path = tmp_path / "no_header.xlsx"

    rows = [
        ["Some", "Other", "Columns"],
        [1, 2, 3],
    ]
    _write_excel(file_path, rows)

    with pytest.raises(ValueError):
        parse_input(file_path)

def test_sample_file_parsed_correctly():
    sample_file = Path(__file__).parent.parent / "samples" / "rico-cc.xlsx"

    df = parse_input(sample_file)

    # Basic checks on the sample data
    assert list(df.columns) == ["Movimentação", "Liquidação", "Lançamento", "Valor", "Saldo"]
    assert not df.empty
