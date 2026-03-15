from pathlib import Path

from firefly_csv_converter.convert_picpay_pdf_ofx_2025 import parse_pdf, process_pdf


def test_parse_pdf_handles_real_2025_sample():
    sample_file = Path("samples-local/picpay/2025-x/2025.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id == "14339269"
    assert statement.start_date.strftime("%Y-%m-%d") == "2025-01-01"
    assert statement.end_date.strftime("%Y-%m-%d") == "2025-12-31"
    assert statement.generated_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-03-11 17:38:00"
    assert len(statement.transactions) == 21

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2025-12-31 20:52:00"
    assert f"{first.amount:.2f}" == "-200.00"
    assert first.memo == "Pix enviado - CAIO COSTA ASSIS"

    assert any(
        transaction.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2025-10-15 14:21:00"
        and f"{transaction.amount:.2f}" == "500.00"
        and transaction.memo == "Pix recebido - RENATO COUTO DA"
        for transaction in statement.transactions
    )

    last = statement.transactions[-1]
    assert last.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2025-06-09 19:03:00"
    assert f"{last.amount:.2f}" == "-30.00"
    assert last.memo == "Pix enviado - Aleatson Fabio Duarte"


def test_process_pdf_generates_ofx_from_real_2025_sample(tmp_path: Path):
    sample_file = Path("samples-local/picpay/2025-x/2025.pdf")
    if not sample_file.exists():
        return

    output_path = tmp_path / "picpay-2025.ofx"
    process_pdf(sample_file, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "<ACCTID>14339269" in content
    assert "<DTSTART>20250609190300" in content
    assert "<DTEND>20251231205200" in content
    assert "<TRNTYPE>DEBIT" in content
    assert "<TRNTYPE>CREDIT" in content
    assert "<NAME>Compra realizada - QMS INTERNACIONAL" in content
    assert "<NAME>Pix recebido - RENATO COUTO DA" in content
