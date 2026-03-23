from pathlib import Path

import pytest

from statement_converter.convert_c6_credit_csv_ofx import (
    parse_csv,
    parse_due_date,
    process_csv,
)


CSV_SAMPLE = """Data de Compra;Nome no Cartão;Final do Cartão;Categoria;Descrição;Parcela;Valor (em US$);Cotação (em R$);Valor (em R$)
27/01/2021;NOME FICTICIO;7076;Marketing Direto;MERCPAGO CROMANIL;2/3;0;0;74.93
05/03/2021;NOME FICTICIO;7360;-;"Inclusao de Pagamento    ";Única;0;0;-628.94
11/03/2021;NOME FICTICIO;7076;Marketing Direto;MERCPAG MERCADOLIVRE;1/2;0;0;57.40
"""


def _write_csv(path: Path, content: str = CSV_SAMPLE) -> None:
    path.write_text(content, encoding="utf-8")


def test_parse_csv_builds_credit_card_statement(tmp_path: Path):
    input_path = tmp_path / "c6-credit.csv"
    _write_csv(input_path)

    statement = parse_csv(input_path)

    assert statement.account_id == "7076-7360"
    assert statement.account_type == "CREDITCARD"
    assert statement.bank_id == "C6"
    assert statement.currency == "BRL"
    assert [transaction.posted_at.strftime("%Y-%m-%d") for transaction in statement.transactions] == [
        "2021-01-27",
        "2021-03-05",
        "2021-03-11",
    ]

    purchase, payment, installment = statement.transactions
    assert f"{purchase.amount:.2f}" == "-74.93"
    assert purchase.name == "MERCPAGO CROMANIL"
    assert purchase.memo == "Parcela: 2/3 | Cartão: 7076"

    assert f"{payment.amount:.2f}" == "628.94"
    assert payment.name == "Inclusao de Pagamento"
    assert payment.memo == "Parcela: Única | Cartão: 7360"

    assert f"{installment.amount:.2f}" == "-57.40"


def test_parse_due_date_accepts_iso_and_br_formats():
    assert parse_due_date("2021-04-05").strftime("%Y%m%d%H%M%S") == "20210405000000"
    assert parse_due_date("05/04/2021").strftime("%Y%m%d%H%M%S") == "20210405000000"


def test_parse_due_date_rejects_unknown_format():
    with pytest.raises(ValueError, match="Due date"):
        parse_due_date("2021/04/05")


def test_process_csv_writes_credit_card_ofx(tmp_path: Path):
    input_path = tmp_path / "c6-credit.csv"
    output_path = tmp_path / "c6-credit.ofx"
    _write_csv(input_path)

    process_csv(input_path, output_path, "2021-04-05")

    content = output_path.read_text(encoding="utf-8")
    assert "OFXHEADER:100" in content
    assert "<CREDITCARDMSGSRSV1>" in content
    assert "<CCSTMTRS>" in content
    assert "<ACCTID>7076-7360" in content
    assert "<DTSTART>20210127000000" in content
    assert "<DTEND>20210311000000" in content
    assert "<TRNAMT>-74.93" in content
    assert "<TRNAMT>628.94" in content
    assert "<NAME>MERCPAGO CROMANIL" in content
    assert "<MEMO>Parcela: Única | Cartão: 7360" in content
    assert "<BALAMT>496.61" in content
    assert "<DTASOF>20210405000000" in content
