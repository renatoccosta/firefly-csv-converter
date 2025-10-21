import csv
import pytest
from pathlib import Path
from src.firefly_csv_converter.convert_bb_lc import parse_input

SAMPLES_DIR = Path(__file__).parent.parent / "samples"

def test_extract_bb_statement_creates_expected_csv():
    """Test if the extractor generates correct CSV output."""
    sample_file = SAMPLES_DIR / "bb-lcilca.txt"

    fieldnames, records = parse_input(sample_file)

    # Validate header
    assert fieldnames == ["Data", "Histórico", "Valor Movimento"]

    # Should have exactly 2 data lines (Aplicação + Rendimento Bruto)
    assert len(records) == 2

    # Validate first row (from table)
    assert records[0][0] == "07/04/2025"
    assert records[0][1] == "Aplicação"
    assert records[0][2] == "30000,00"

    # Validate second row (from summary)
    assert records[1][0] == "30/04/2025"
    assert records[1][1] == "Rendimento Bruto"
    assert records[1][2] == "220,59"

    # Ensure "Saldo Anterior" and "Saldo Atual" were ignored
    historicos = [row[1].lower() for row in records]
    assert not any("saldo" in h for h in historicos)
