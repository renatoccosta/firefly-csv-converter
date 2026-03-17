from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from firefly_csv_converter.convert_rico_xlsx_ofx import parse_input, process_ofx


def _write_excel(path: Path, rows):
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False, header=False)


def test_parse_input_builds_statement_data(tmp_path):
    file_path = tmp_path / "rico_ofx.xlsx"
    rows = [
        [None, None, None, None, None, None, "Data da consulta: 05/10/2025 00:08"],
        [None, None, None, None, None, None, "Conta Rico: 12312312"],
        [None, None, None, None, None, None, None],
        [None, "Movimentação", "Liquidação", "Lançamento", None, "Valor (R$)", "Saldo (R$)"],
        [None, pd.Timestamp("2025-01-03"), pd.Timestamp("2025-01-04"), "COMPRA TESTE", None, -10.55, 120.10],
        [None, pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-06"), "CREDITO TESTE", None, 22.00, 142.10],
    ]
    _write_excel(file_path, rows)

    statement = parse_input(file_path)

    assert statement.account_id == "12312312"
    assert statement.bank_id == "RICO"
    assert statement.currency == "BRL"
    assert statement.generated_at == datetime(2025, 10, 5, 0, 8)
    assert len(statement.transactions) == 2

    first, second = statement.transactions
    assert first.posted_at == datetime(2025, 1, 4, 0, 0)
    assert first.amount == Decimal("-10.55")
    assert first.balance == Decimal("120.10")
    assert first.memo == "COMPRA TESTE"
    assert second.amount == Decimal("22.00")


def test_parse_input_uses_movimentacao_when_liquidacao_missing(tmp_path):
    file_path = tmp_path / "rico_missing_liquidacao.xlsx"
    rows = [
        [None, "Movimentação", "Liquidação", "Lançamento", None, "Valor (R$)", "Saldo (R$)"],
        [None, pd.Timestamp("2025-02-10"), None, "SEM LIQUIDACAO", None, 15.0, 15.0],
    ]
    _write_excel(file_path, rows)

    statement = parse_input(file_path)

    assert statement.transactions[0].posted_at.date() == date(2025, 2, 10)


def test_parse_input_raises_when_there_are_no_transactions(tmp_path):
    file_path = tmp_path / "rico_empty.xlsx"
    rows = [
        [None, "Movimentação", "Liquidação", "Lançamento", None, "Valor (R$)", "Saldo (R$)"],
        [None, None, None, "Não há lançamentos para o período", None, None, None],
    ]
    _write_excel(file_path, rows)

    with pytest.raises(ValueError, match="No transactions"):
        parse_input(file_path)


def test_process_ofx_writes_expected_output(tmp_path):
    input_path = Path(__file__).parent.parent / "samples" / "rico-cc.xlsx"
    output_path = tmp_path / "rico.ofx"

    process_ofx(input_path, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "OFXHEADER:100" in content
    assert "<BANKID>RICO" in content
    assert "<ACCTID>12312312" in content
    assert "<DTSERVER>20251005000800" in content
    assert "<DTSTART>20250102000000" in content
    assert "<DTEND>20250925000000" in content
    assert "<TRNAMT>-15908.79" in content
    assert "<TRNAMT>187.68" in content
    assert "<MEMO>COMPRA TESOURO DIRETO CLIENTES" in content
