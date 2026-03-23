import zlib
from datetime import datetime
from pathlib import Path

from statement_converter.convert_c6_credit_pdf_ofx import (
    infer_transaction_year,
    is_credit_transaction,
    parse_due_date,
    parse_pdf_document,
    process_pdf,
)


GRAY = (0.45098, 0.45098, 0.45098)
GREEN = (0.0, 0.47451, 0.42353)
DARK = (0.24314, 0.24314, 0.24314)


def encode_pdf_text(text: str) -> bytes:
    return text.encode("latin1", "replace").replace(b"\\", b"\\\\").replace(b"(", rb"\(").replace(b")", rb"\)")


def make_text_block(x: float, y: float, text: str, color: tuple[float, float, float] | None = None) -> bytes:
    color_prefix = b""
    if color is not None:
        color_prefix = f"{color[0]:.5f} {color[1]:.5f} {color[2]:.5f} rg\n".encode()

    return (
        b"BT\n"
        + f"1 0 0 1 {x:.2f} {y:.2f} Tm\n".encode()
        + color_prefix
        + b"("
        + encode_pdf_text(text)
        + b")Tj\nET\n"
    )


def make_pdf_like_bytes(text_elements: list[tuple[float, float, str, tuple[float, float, float] | None]]) -> bytes:
    content = b"".join(make_text_block(x, y, text, color) for x, y, text, color in text_elements)
    compressed = zlib.compress(content)
    return b"%%PDF-1.4\n1 0 obj\n<< /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream\n%%%%EOF" % (
        len(compressed),
        compressed,
    )


def build_c6_pdf_fixture() -> bytes:
    return make_pdf_like_bytes(
        [
            (189.0, 791.3, "Vencimento: 05 de Janeiro", GRAY),
            (53.0, 709.81, "Transações do cartão principal", DARK),
            (53.0, 692.16, "Lembrando: nesta fatura serão lançadas apenas transações feitas até 22/12/24.", GRAY),
            (58.0, 640.58, "Cartão C6 Final 1111 - NOME FICTICIO", DARK),
            (38.0, 569.3, "29 dez", GRAY),
            (100.0, 569.3, "LOJA TESTE - Parcela 3/4", GRAY),
            (525.57, 569.3, "46,42", GRAY),
            (38.0, 544.3, "02 nov", GRAY),
            (100.0, 544.3, "COMPRA AJUSTADA - Estorno", GREEN),
            (529.95, 544.3, "20,00", GREEN),
            (58.0, 500.58, "Cartão C6 Final 2222 - NOME FICTICIO", DARK),
            (38.0, 469.3, "20 dez", GREEN),
            (100.0, 469.3, "Inclusao de Pagamento", GREEN),
            (526.86, 469.3, "316,81", GREEN),
        ]
    )


def test_infer_transaction_year_uses_previous_year_after_statement_cutoff():
    reference_date = datetime(2024, 3, 28)

    assert infer_transaction_year(29, 12, "COMPRA TESTE", reference_date) == 2023


def test_infer_transaction_year_handles_installments_before_cutoff_month():
    reference_date = datetime(2024, 3, 28)

    assert infer_transaction_year(3, 1, "LOJA TESTE - Parcela 12/12", reference_date) == 2023


def test_parse_due_date_rolls_over_year_when_month_is_before_cutoff():
    reference_date = datetime(2024, 12, 22)

    due_date = parse_due_date("05 de Janeiro", reference_date)

    assert due_date.strftime("%Y-%m-%d") == "2025-01-05"


def test_is_credit_transaction_recognizes_payment_and_estorno():
    assert is_credit_transaction("Inclusao de Pagamento")
    assert is_credit_transaction("COMPRA TESTE - Estorno")
    assert not is_credit_transaction("COMPRA NORMAL")


def test_parse_pdf_document_handles_synthetic_c6_invoice(tmp_path: Path):
    input_path = tmp_path / "c6-credit.pdf"
    input_path.write_bytes(build_c6_pdf_fixture())

    statement, due_date = parse_pdf_document(input_path)

    assert due_date.strftime("%Y-%m-%d") == "2025-01-05"
    assert statement.account_id == "1111-2222"
    assert len(statement.transactions) == 3
    assert sum(1 for transaction in statement.transactions if transaction.amount > 0) == 2

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d") == "2024-11-02"
    assert first.name == "COMPRA AJUSTADA"
    assert first.memo == "Estorno | Cartão: 1111"
    assert f"{first.amount:.2f}" == "20.00"

    installment = next(transaction for transaction in statement.transactions if "Parcela" in transaction.memo)
    assert installment.posted_at.strftime("%Y-%m-%d") == "2024-12-29"
    assert installment.name == "LOJA TESTE"
    assert installment.memo == "Parcela: 3/4 | Cartão: 1111"
    assert f"{installment.amount:.2f}" == "-46.42"

    payment = next(transaction for transaction in statement.transactions if transaction.name == "Inclusao de Pagamento")
    assert payment.posted_at.strftime("%Y-%m-%d") == "2024-12-20"
    assert payment.memo == "Cartão: 2222"
    assert f"{payment.amount:.2f}" == "316.81"


def test_process_pdf_writes_credit_card_ofx_from_synthetic_invoice(tmp_path: Path):
    input_path = tmp_path / "c6-credit.pdf"
    output_path = tmp_path / "c6-credit.ofx"
    input_path.write_bytes(build_c6_pdf_fixture())

    process_pdf(input_path, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "OFXHEADER:100" in content
    assert "<CREDITCARDMSGSRSV1>" in content
    assert "<ACCTID>1111-2222" in content
    assert "<DTSTART>20241102000000" in content
    assert "<DTEND>20241229000000" in content
    assert "<DTASOF>20250105000000" in content
    assert "<TRNAMT>20.00" in content
    assert "<TRNAMT>-46.42" in content
    assert "<TRNAMT>316.81" in content
    assert "<NAME>LOJA TESTE" in content
