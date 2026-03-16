from pathlib import Path

from firefly_csv_converter.convert_vr_pdf_ofx import parse_pdf, process_pdf


def test_parse_pdf_handles_real_2024_vr_sample():
    sample_file = Path("samples-local/vr/2024.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id == "6370360025871465"
    assert len(statement.transactions) == 84
    assert len([transaction for transaction in statement.transactions if transaction.amount > 0]) == 5

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2024-01-03 20:01:56"
    assert f"{first.amount:.2f}" == "-236.81"
    assert first.name == "SENDAS DISTRIBUIDORA S/A - ASSAÍ ATACADISTA"
    assert first.memo == "Consumo Confirmado"

    assert any(
        transaction.name == "PETROLEO BRASILEIRO S.A. - PETROBRAS"
        and transaction.memo == "Disponibilização Benefício Usuário"
        and f"{transaction.amount:.2f}" == "1377.76"
        for transaction in statement.transactions
    )
    assert statement.transactions[-1].posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2024-07-04 20:07:10"
    assert statement.transactions[-1].memo == "Consumo Confirmado"


def test_parse_pdf_handles_real_2023_vr_sample():
    sample_file = Path("samples-local/vr/2023.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id == "6370360025871465"
    assert len(statement.transactions) == 147
    assert len([transaction for transaction in statement.transactions if transaction.amount > 0]) == 13
    assert statement.transactions[-1].posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2023-12-30 16:12:27"
    assert statement.transactions[-1].name == "HIPERIDEAL EMPREENDIMENTOS LTDA - HIPERIDEAL"
    assert statement.transactions[-1].memo == "Consumo Confirmado"


def test_parse_pdf_handles_real_2020_2022_vr_sample():
    sample_file = Path("samples-local/vr/2020-2022.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id == "6370360025871465"
    assert len(statement.transactions) == 406
    assert len([transaction for transaction in statement.transactions if transaction.amount > 0]) == 40

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2020-02-21 00:00:00"
    assert f"{first.amount:.2f}" == "702.58"
    assert first.name == "PETROLEO BRASILEIRO S.A. - PETROBRAS"
    assert first.memo == "Disponibilização Benefício Usuário"

    last = statement.transactions[-1]
    assert last.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2023-06-02 00:00:00"
    assert f"{last.amount:.2f}" == "-53.29"
    assert last.name == "AMERICANAS S.A. - HORTIFRUTI CONDE 99"
    assert last.memo == "Consumo Confirmado"


def test_process_pdf_generates_ofx_from_real_vr_sample(tmp_path: Path):
    sample_file = Path("samples-local/vr/2024.pdf")
    if not sample_file.exists():
        return

    output_path = tmp_path / "vr-2024.ofx"
    process_pdf(sample_file, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "<BANKID>VR" in content
    assert "<ACCTID>6370360025871465" in content
    assert "<DTSTART>20240103200156" in content
    assert "<DTEND>20240704200710" in content
    assert "<TRNTYPE>DEBIT" in content
    assert "<TRNTYPE>CREDIT" in content
    assert "<NAME>SENDAS DISTRIBUIDORA S/A - ASSAÍ ATACADISTA" in content
    assert "<MEMO>Consumo Confirmado" in content


def test_process_pdf_generates_ofx_from_real_vr_2020_2022_sample(tmp_path: Path):
    sample_file = Path("samples-local/vr/2020-2022.pdf")
    if not sample_file.exists():
        return

    output_path = tmp_path / "vr-2020-2022.ofx"
    process_pdf(sample_file, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "<DTSTART>20200221000000" in content
    assert "<DTEND>20230602000000" in content
    assert "<TRNAMT>702.58" in content
    assert "<TRNAMT>-53.29" in content
    assert "<MEMO>Disponibilização Benefício Usuário" in content
