from datetime import datetime
from decimal import Decimal
from pathlib import Path

from statement_converter._ofx_common import StatementData, StatementTransaction
from statement_converter.convert_bb_cc_pdf_ofx import (
    TextElement,
    is_balance_label,
    parse_elements,
    process_pdf,
)


def build_page(*elements: TextElement) -> list[TextElement]:
    return list(elements)


def test_is_balance_label_accepts_supported_variants():
    assert is_balance_label("Saldo Anterior")
    assert is_balance_label("S A L D O")
    assert not is_balance_label("Pix - Enviado")


def test_parse_elements_maps_columns_multiline_history_and_colors():
    page = build_page(
        TextElement(137.63, 787.98, "SISBB - Sistema de Informações Banco do Brasil - 05/01/2024 - Autoatendimento BB - 11:35:50", (0.29, 0.29, 0.29)),
        TextElement(171.44, 779.28, "Agência: 1234-5   Conta: 67890-1   Cliente:", (0.29, 0.29, 0.29)),
        TextElement(322.88, 779.28, "PESSOA FICTICIA", (0.29, 0.29, 0.29)),
        TextElement(44.86, 736.43, "29/12/2023", (0.29, 0.29, 0.29)),
        TextElement(162.72, 736.43, "Saldo Anterior", (0.29, 0.29, 0.29)),
        TextElement(475.81, 736.30, "1.000,00 C", (0.0, 0.53333, 0.73333)),
        TextElement(44.86, 720.58, "02/01/2024", (0.29, 0.29, 0.29)),
        TextElement(101.66, 720.58, "1234-5", (0.29, 0.29, 0.29)),
        TextElement(162.72, 724.91, "Pix - Enviado", (0.29, 0.29, 0.29)),
        TextElement(162.72, 716.22, "02/01 09:30 FULANO DE TAL", (0.29, 0.29, 0.29)),
        TextElement(162.72, 707.52, "CPF 000.000.000-00", (0.29, 0.29, 0.29)),
        TextElement(303.75, 720.58, "123.456", (0.29, 0.29, 0.29)),
        TextElement(419.42, 720.58, "150,45 D", (1.0, 0.0, 0.03922)),
        TextElement(44.86, 694.00, "03/01/2024", (0.29, 0.29, 0.29)),
        TextElement(162.72, 698.33, "Recebimento de Proventos", (0.29, 0.29, 0.29)),
        TextElement(162.72, 689.64, "EMPRESA FICTICIA SA", (0.29, 0.29, 0.29)),
        TextElement(303.75, 694.00, "2.598", (0.29, 0.29, 0.29)),
        TextElement(413.15, 694.00, "8.806,39 C", (0.0, 0.53333, 0.73333)),
        TextElement(44.86, 670.00, "31/01/2024", (0.29, 0.29, 0.29)),
        TextElement(162.72, 670.00, "S A L D O", (0.29, 0.29, 0.29)),
        TextElement(475.81, 669.86, "9.655,94 C", (0.0, 0.53333, 0.73333)),
    )

    statement = parse_elements([page])

    assert statement.account_id == "67890-1"
    assert statement.bank_id == "001"
    assert statement.generated_at.strftime("%Y-%m-%d %H:%M:%S") == "2024-01-05 11:35:50"
    assert len(statement.transactions) == 2

    debit = statement.transactions[0]
    assert debit.posted_at.strftime("%Y-%m-%d") == "2024-01-02"
    assert debit.name == "Pix - Enviado"
    assert debit.memo == "1234-5 | 123.456 | 02/01 09:30 FULANO DE TAL | CPF 000.000.000-00"
    assert f"{debit.amount:.2f}" == "-150.45"

    credit = statement.transactions[1]
    assert credit.name == "Recebimento de Proventos"
    assert credit.memo == "2.598 | EMPRESA FICTICIA SA"
    assert f"{credit.amount:.2f}" == "8806.39"


def test_process_pdf_generates_ofx(monkeypatch, tmp_path: Path):
    def fake_parse_pdf(_input_path: Path) -> StatementData:
        return StatementData(
            account_id="67890-1",
            account_type="CHECKING",
            bank_id="001",
            currency="BRL",
            generated_at=datetime(2024, 1, 5, 11, 35, 50),
            start_date=None,
            end_date=None,
            transactions=[
                StatementTransaction(
                    posted_at=datetime(2024, 1, 2, 0, 0, 0),
                    name="Pix - Enviado",
                    memo="1234-5 | 123.456 | 02/01 09:30 FULANO DE TAL",
                    amount=Decimal("-150.45"),
                    balance=None,
                ),
                StatementTransaction(
                    posted_at=datetime(2024, 1, 3, 0, 0, 0),
                    name="Recebimento de Proventos",
                    memo="2.598 | EMPRESA FICTICIA SA",
                    amount=Decimal("8806.39"),
                    balance=None,
                ),
            ],
        )

    monkeypatch.setattr("statement_converter.convert_bb_cc_pdf_ofx.parse_pdf", fake_parse_pdf)

    sample_file = tmp_path / "entrada.pdf"
    sample_file.write_bytes(b"%PDF-1.4 synthetic")
    output_path = tmp_path / "bb-cc.ofx"
    process_pdf(sample_file, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "OFXHEADER:100" in content
    assert "<BANKMSGSRSV1>" in content
    assert "<BANKID>001" in content
    assert "<ACCTID>67890-1" in content
    assert "<TRNTYPE>DEBIT" in content
    assert "<TRNTYPE>CREDIT" in content
    assert "<NAME>Recebimento de Proventos" in content
    assert "<MEMO>2.598 | EMPRESA FICTICIA SA" in content
