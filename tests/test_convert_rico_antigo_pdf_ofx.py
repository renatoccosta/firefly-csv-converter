from pathlib import Path

import pytest

from statement_converter.convert_rico_antigo_pdf_ofx import parse_pdf, parse_statement_text, process_pdf


SYNTHETIC_TEXT = """Meu Extrato
Saldo disponível R$ 99.999,99 Mais detalhes
Lançamentos Conta Antiga
Completo
01/01/20 - 31/12/20
Evento Valor (R$) Saldo (R$)
30/12/2020
Débito COMPRA TESTE -10,00 90,00
Crédito DIVIDENDO ABC 5,55 95,55
29/12/2020
Crédito TED DE TESTE 100,00 100,00
Sua Conta Rico
Banco
102
Agência
0001
Conta
12345-6
1 de 4
Extrato para simples conferência, sujeito a atualizações.
Débito AJUSTE DE TESTE 20,00 80,00
"""


def test_parse_statement_text_extracts_transactions_period_and_account_id():
    statement = parse_statement_text(SYNTHETIC_TEXT)

    assert statement.account_id == "12345-6"
    assert statement.bank_id == "RICO"
    assert statement.start_date.strftime("%Y-%m-%d") == "2020-01-01"
    assert statement.end_date.strftime("%Y-%m-%d") == "2020-12-31"
    assert len(statement.transactions) == 4

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d") == "2020-12-29"
    assert first.name == "TED DE TESTE"
    assert first.memo == "TED DE TESTE"
    assert f"{first.amount:.2f}" == "100.00"
    assert f"{first.balance:.2f}" == "100.00"

    second = statement.transactions[1]
    assert second.posted_at.strftime("%Y-%m-%d") == "2020-12-29"
    assert second.memo == "AJUSTE DE TESTE"
    assert f"{second.amount:.2f}" == "-20.00"
    assert f"{second.balance:.2f}" == "80.00"

    third = statement.transactions[2]
    assert third.memo == "COMPRA TESTE"
    assert f"{third.amount:.2f}" == "-10.00"

    fourth = statement.transactions[3]
    assert fourth.memo == "DIVIDENDO ABC"
    assert f"{fourth.amount:.2f}" == "5.55"


def test_parse_statement_text_ignores_noise_and_requires_transactions():
    text = """Meu Extrato
Saldo disponível R$ 10,00
Lançamentos Conta Antiga
Conta
12345-6
"""

    with pytest.raises(ValueError, match="No transactions"):
        parse_statement_text(text)


def test_parse_pdf_uses_extracted_text(monkeypatch):
    monkeypatch.setattr(
        "statement_converter.convert_rico_antigo_pdf_ofx.extract_pdf_text",
        lambda _: SYNTHETIC_TEXT,
    )

    statement = parse_pdf(Path("dummy.pdf"))

    assert statement.account_id == "12345-6"
    assert len(statement.transactions) == 4


def test_process_pdf_generates_expected_ofx(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "statement_converter.convert_rico_antigo_pdf_ofx.extract_pdf_text",
        lambda _: SYNTHETIC_TEXT,
    )

    output_path = tmp_path / "rico-antigo.ofx"
    process_pdf(Path("dummy.pdf"), output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "OFXHEADER:100" in content
    assert "<BANKID>RICO" in content
    assert "<ACCTID>12345-6" in content
    assert "<DTSTART>20201229000000" in content
    assert "<DTEND>20201230000000" in content
    assert "<NAME>TED DE TESTE" in content
    assert "<MEMO>AJUSTE DE TESTE" in content
    assert "<TRNAMT>100.00" in content
    assert "<TRNAMT>-20.00" in content
