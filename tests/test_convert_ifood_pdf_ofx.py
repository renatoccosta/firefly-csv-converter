from pathlib import Path

from statement_converter.convert_ifood_pdf_ofx import parse_pdf, process_pdf


def test_parse_pdf_handles_real_ifood_sample():
    sample_file = Path("samples-local/ifood/extrato.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id == "IFOOD"
    assert len(statement.transactions) == 551

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2024-06-25 00:02:22"
    assert first.name == "Crédito de Benefício"
    assert first.memo == "Alimentação"
    assert f"{first.amount:.2f}" == "918.51"

    last = statement.transactions[-1]
    assert last.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-03-10 13:10:41"
    assert last.name == "AbelhimDoces"
    assert last.memo == "Refeição"
    assert f"{last.amount:.2f}" == "-20.00"

    missing_name_regression = next(
        transaction
        for transaction in statement.transactions
        if transaction.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-02-16 17:02:33"
    )
    assert missing_name_regression.name == "LANCHONETES ACQUA"


def test_process_pdf_generates_ofx_from_real_ifood_sample(tmp_path: Path):
    sample_file = Path("samples-local/ifood/extrato.pdf")
    if not sample_file.exists():
        return

    output_path = tmp_path / "ifood.ofx"
    process_pdf(sample_file, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "<BANKID>IFOOD" in content
    assert "<ACCTID>IFOOD" in content
    assert "<DTSTART>20240625000222" in content
    assert "<DTEND>20260310131041" in content
    assert "<NAME>Crédito de Benefício" in content
    assert "<MEMO>Refeição" in content
    assert "<NAME>LANCHONETES ACQUA" in content
