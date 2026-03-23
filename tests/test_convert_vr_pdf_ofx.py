from pathlib import Path

from statement_converter.convert_vr_pdf_ofx import parse_pdf, process_pdf


def test_parse_pdf_handles_real_2024_vr_sample():
    sample_file = Path("samples-local/vr/2024.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id.isdigit()
    assert len(statement.account_id) >= 12
    assert len(statement.transactions) == 79
    assert len([transaction for transaction in statement.transactions if transaction.amount > 0]) == 5

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2024-01-01 14:01:46"
    assert f"{first.amount:.2f}" == "-250.00"
    assert first.name == "JG SILVEIRA RESTAURANTE LTDA - KI-MUKEKA PITUBA"
    assert first.memo == "Consumo Confirmado"

    assert any(
        transaction.name == "PETROLEO BRASILEIRO S.A. - PETROBRAS"
        and transaction.memo == "Disponibilização Benefício Usuário"
        and f"{transaction.amount:.2f}" == "459.26"
        for transaction in statement.transactions
    )
    assert statement.transactions[-1].posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2024-07-28 13:07:13"
    assert statement.transactions[-1].memo == "Consumo Confirmado"


def test_parse_pdf_handles_real_2023_vr_sample():
    sample_file = Path("samples-local/vr/2023.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id.isdigit()
    assert len(statement.account_id) >= 12
    assert len(statement.transactions) == 169
    assert len([transaction for transaction in statement.transactions if transaction.amount > 0]) == 12
    assert statement.transactions[0].posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2023-01-04 10:01:25"
    assert statement.transactions[0].name == "CASA DO ALEMAO IND E COM DE LANCHE LTDA - CASA DO ALEMÃO"
    assert statement.transactions[-1].posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2023-12-22 09:12:50"
    assert statement.transactions[-1].name == "PROJETO VR VIRA"
    assert statement.transactions[-1].memo == "Vem com VR"


def test_parse_pdf_handles_real_2020_2022_vr_sample():
    sample_file = Path("samples-local/vr/2020-2022.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id.isdigit()
    assert len(statement.account_id) >= 12
    assert len(statement.transactions) == 352
    assert len([transaction for transaction in statement.transactions if transaction.amount > 0]) == 38

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2020-02-21 00:00:00"
    assert f"{first.amount:.2f}" == "702.59"
    assert first.name == "PETROLEO BRASILEIRO S.A. - PETROBRAS"
    assert first.memo == "Disponibilização Benefício Usuário"

    last = statement.transactions[-1]
    assert last.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2023-05-31 00:00:00"
    assert f"{last.amount:.2f}" == "-33.10"
    assert last.name == "NOVO BAR E RESTAURANTE MARACANA LTDA - BAKANA"
    assert last.memo == "Consumo Confirmado"


def test_process_pdf_generates_ofx_from_real_vr_sample(tmp_path: Path):
    sample_file = Path("samples-local/vr/2024.pdf")
    if not sample_file.exists():
        return

    output_path = tmp_path / "vr-2024.ofx"
    process_pdf(sample_file, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "<BANKID>VR" in content
    assert "<ACCTID>" in content
    assert "<DTSTART>20240101140146" in content
    assert "<DTEND>20240728130713" in content
    assert "<TRNTYPE>DEBIT" in content
    assert "<TRNTYPE>CREDIT" in content
    assert "<NAME>JG SILVEIRA RESTAURANTE LTDA - KI-MUKEKA PITUBA" in content
    assert "<MEMO>Consumo Confirmado" in content


def test_process_pdf_generates_ofx_from_real_vr_2020_2022_sample(tmp_path: Path):
    sample_file = Path("samples-local/vr/2020-2022.pdf")
    if not sample_file.exists():
        return

    output_path = tmp_path / "vr-2020-2022.ofx"
    process_pdf(sample_file, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "<DTSTART>20200221000000" in content
    assert "<DTEND>20230531000000" in content
    assert "<TRNAMT>702.59" in content
    assert "<TRNAMT>-33.10" in content
    assert "<MEMO>Disponibilização Benefício Usuário" in content
