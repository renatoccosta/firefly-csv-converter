import os
from pathlib import Path
import pytest
from src.firefly_csv_converter.convert_bb_cp import parse_csv 

SAMPLES_DIR = Path(__file__).parent.parent / "samples"

def test_parse_csv_bb_cp():
    sample_file = SAMPLES_DIR / "bb-cp.csv"

    fieldnames, records = parse_csv(sample_file)

    # Garantir que os campos esperados estão presentes
    assert "Valor" in fieldnames
    assert "Type" in fieldnames

    # Garantir que pelo menos uma linha foi lida
    assert len(records) > 0

    # Verificar se a coluna "Type" foi corretamente separada
    first_row = records[0]
    assert "Valor" in first_row
    assert "Type" in first_row

    # Deve ter o formato "123,45" e "C" ou "D"
    assert first_row["Valor"].replace(",", "").replace(".", "").isdigit()
    assert first_row["Type"] in ("C", "D", "")