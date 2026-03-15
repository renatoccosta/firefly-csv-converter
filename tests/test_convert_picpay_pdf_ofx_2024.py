import zlib
from datetime import datetime
from pathlib import Path

from firefly_csv_converter._picpay_ofx_common import StatementData, build_ofx
from firefly_csv_converter.convert_picpay_pdf_ofx_2024 import (
    parse_pdf,
    process_pdf,
)


def encode_pdf_text(text: str) -> bytes:
    return text.encode("utf-16-be").replace(b"\\", b"\\\\").replace(b"(", rb"\(").replace(b")", rb"\)")


def make_text_command(x: float, y: float, text: str) -> bytes:
    return f"{x:.3f} {y:.3f} Td ".encode() + b"(" + encode_pdf_text(text) + b") Tj\n"


def make_pdf_like_bytes(text_elements: list[tuple[float, float, str]]) -> bytes:
    content = b"".join(make_text_command(x, y, text) for x, y, text in text_elements)
    compressed = zlib.compress(content)
    return b"%%PDF-1.4\n1 0 obj\n<< /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream\n%%%%EOF" % (
        len(compressed),
        compressed,
    )


def test_parse_pdf_extracts_transactions_and_metadata(tmp_path: Path):
    pdf_bytes = make_pdf_like_bytes(
        [
            (493.230, 719.850, "Conta:"),
            (529.520, 719.850, "14339269"),
            (266.052, 642.958, "1 DE JANEIRO DE 2024 A 31 DE DEZEMBRO DE 2024"),
            (421.928, -0.568, "Extrato gerado em 11/03/2026 às 17:47:35"),
            (17.000, 642.958, "MOVIMENTAÇÕES"),
            (47.929, 557.622, "Data/Hora"),
            (132.995, 557.622, "Descrição das Movimentações"),
            (349.444, 557.622, "Valor"),
            (427.276, 557.622, "Saldo"),
            (500.601, 557.622, "Saldo Sacável"),
            (47.769, 512.422, "29/07/2024"),
            (52.345, 502.822, "01:27:18"),
            (132.995, 507.622, "Pix Enviado"),
            (341.464, 507.622, "- R$ 25,00"),
            (420.060, 507.622, "R$ 264,25"),
            (510.233, 507.622, "R$ 264,25"),
            (47.769, 462.422, "28/07/2024"),
            (52.345, 452.822, "08:00:00"),
            (132.995, 457.622, "Pix Recebido"),
            (341.464, 457.622, "R$ 100,00"),
            (438.515, 457.622, "-"),
            (528.369, 457.622, "-"),
        ]
    )
    input_path = tmp_path / "picpay.pdf"
    input_path.write_bytes(pdf_bytes)

    statement = parse_pdf(input_path)

    assert statement.account_id == "14339269"
    assert statement.start_date.strftime("%Y-%m-%d") == "2024-01-01"
    assert statement.end_date.strftime("%Y-%m-%d") == "2024-12-31"
    assert statement.generated_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-03-11 17:47:35"
    assert len(statement.transactions) == 2

    first = statement.transactions[0]
    assert first.memo == "Pix Enviado"
    assert f"{first.amount:.2f}" == "-25.00"
    assert f"{first.balance:.2f}" == "264.25"
    assert first.posted_at.strftime("%Y-%m-%d %H:%M:%S") == "2024-07-29 01:27:18"

    second = statement.transactions[1]
    assert second.memo == "Pix Recebido"
    assert f"{second.amount:.2f}" == "100.00"
    assert second.balance is None


def test_process_pdf_generates_ofx_file(tmp_path: Path):
    pdf_bytes = make_pdf_like_bytes(
        [
            (493.230, 719.850, "Conta:"),
            (529.520, 719.850, "14339269"),
            (266.052, 642.958, "1 DE JANEIRO DE 2023 A 31 DE DEZEMBRO DE 2023"),
            (421.928, -0.568, "Extrato gerado em 14/01/2024 às 00:37:29"),
            (17.000, 642.958, "MOVIMENTAÇÕES"),
            (49.428, 557.622, "Data/Hora"),
            (135.992, 557.622, "Descrição das Movimentações"),
            (348.767, 557.622, "Valor"),
            (428.515, 557.622, "Saldo"),
            (501.521, 557.622, "Saldo Sacável"),
            (49.268, 512.422, "28/03/2023"),
            (53.844, 502.822, "14:49:30"),
            (135.992, 507.622, "Pix Recebido"),
            (340.943, 507.622, "R$ 300,00"),
            (421.299, 507.622, "R$ 569,15"),
            (511.153, 507.622, "R$ 569,15"),
            (49.268, 462.422, "20/03/2023"),
            (53.844, 452.822, "15:03:00"),
            (135.992, 457.622, "Pix Enviado"),
            (340.787, 457.622, "- R$ 12,00"),
            (421.299, 457.622, "R$ 269,15"),
            (511.153, 457.622, "R$ 269,15"),
        ]
    )
    input_path = tmp_path / "picpay-2023.pdf"
    output_path = tmp_path / "picpay-2023.ofx"
    input_path.write_bytes(pdf_bytes)

    process_pdf(input_path, output_path)

    content = output_path.read_text(encoding="utf-8")

    assert "<BANKID>PICPAY" in content
    assert "<ACCTID>14339269" in content
    assert "<CURDEF>BRL" in content
    assert "<TRNTYPE>CREDIT" in content
    assert "<TRNTYPE>DEBIT" in content
    assert "<TRNAMT>300.00" in content
    assert "<TRNAMT>-12.00" in content
    assert "<NAME>Pix Recebido" in content
    assert "<NAME>Pix Enviado" in content
    assert "<BALAMT>269.15" in content


def test_build_ofx_handles_empty_transactions():
    content = build_ofx(
        StatementData(
            account_id="14339269",
            account_type="CHECKING",
            bank_id="PICPAY",
            currency="BRL",
            generated_at=datetime(2026, 3, 11, 17, 47, 35),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            transactions=[],
        )
    )
    assert "<BANKTRANLIST>" in content
    assert "<DTSTART>20240101000000" in content
    assert "<DTEND>20241231000000" in content
    assert "<BALAMT>0.00" in content
