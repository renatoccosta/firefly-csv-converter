from pathlib import Path

from firefly_csv_converter.convert_pb_pdf_ofx import parse_pdf, parse_row, parse_statement_text, process_pdf


SYNTHETIC_TEXT = """PETRÓLEO BRASILEIRO S.A.
COMPROVANTE DE
DEPÓSITO BANCÁRIO
Contracheque do Mês
Pessoa Fictícia
Nome
1234567
Matrícula
07/2025
Mês/Ano
25/07/2025
Disponível
Código Descrição Quantidade Valor
0001 Salário Básico 18 R$ 8.797,61
0192 Complemento da RMNR  R$ 6.589,49
1215 Gratif Férias C/Pet 1/3 12 R$ 3.908,11
R$ 19.295,21Total de Proventos ...............
0927 Imposto de Renda 27,5 R$ 3.897,79
5636 Desc Adiant sal sem IR  R$ 7.860,19
R$ 11.757,98Total de Descontos ...............
R$ 7.537,23
Total Líquido
R$ 8.503,02
Valor Líquido Depositado
"""


PROVENTOS_ONLY_TEXT = """PETRÓLEO BRASILEIRO S.A.
Adiantamento
1234567
Matrícula
10/02/2022
Disponível
Código Descrição Quantidade Valor
0636 Adiant salarial sem IR 45 R$ 7.961,75
R$ 7.961,75Total de Proventos ...............
R$ 7.961,75
Valor Líquido Depositado
"""


def test_parse_row_handles_quantity_and_description_suffix():
    row = parse_row("1215 Gratif Férias C/Pet 1/3 12 R$ 3.908,11")

    assert row is not None
    assert row.code == "1215"
    assert row.description == "Gratif Férias C/Pet 1/3"
    assert row.quantity == "12"
    assert f"{row.amount:.2f}" == "3908.11"


def test_parse_statement_text_builds_credit_debit_and_net_deposit_transactions():
    statement = parse_statement_text(SYNTHETIC_TEXT)

    assert statement.account_id == "1234567"
    assert statement.account_type == "CHECKING"
    assert statement.bank_id == "PB"
    assert len(statement.transactions) == 6

    salary = statement.transactions[0]
    assert salary.posted_at.strftime("%Y-%m-%d") == "2025-07-25"
    assert salary.name == "Salário Básico"
    assert salary.memo == "Código: 0001 | Quantidade: 18"
    assert f"{salary.amount:.2f}" == "8797.61"

    complemento = statement.transactions[1]
    assert complemento.name == "Complemento da RMNR"
    assert complemento.memo == "Código: 0192"
    assert f"{complemento.amount:.2f}" == "6589.49"

    desconto = statement.transactions[3]
    assert desconto.name == "Imposto de Renda"
    assert desconto.memo == "Código: 0927 | Quantidade: 27,5"
    assert f"{desconto.amount:.2f}" == "-3897.79"

    liquido = statement.transactions[-1]
    assert liquido.name == "Valor Líquido Depositado"
    assert liquido.memo == "Resumo do contracheque PB"
    assert f"{liquido.amount:.2f}" == "-8503.02"


def test_parse_statement_text_handles_documents_without_discount_group():
    statement = parse_statement_text(PROVENTOS_ONLY_TEXT)

    assert len(statement.transactions) == 2
    assert statement.transactions[0].name == "Adiant salarial sem IR"
    assert statement.transactions[0].memo == "Código: 0636 | Quantidade: 45"
    assert f"{statement.transactions[0].amount:.2f}" == "7961.75"
    assert f"{statement.transactions[1].amount:.2f}" == "-7961.75"


def test_parse_pdf_handles_real_pb_sample_when_available():
    sample_file = Path("samples-local/pb/09746219-202507-Contracheque do M#s.pdf")
    if not sample_file.exists():
        return

    statement = parse_pdf(sample_file)

    assert statement.account_id.isdigit()
    assert len(statement.account_id) == 7
    assert len(statement.transactions) == 22

    first = statement.transactions[0]
    assert first.posted_at.strftime("%Y-%m-%d") == "2025-07-25"
    assert first.name == "Salário Básico"
    assert first.memo == "Código: 0001 | Quantidade: 18"
    assert f"{first.amount:.2f}" == "8797.61"

    desconto = next(transaction for transaction in statement.transactions if transaction.name == "Imp Renda Férias")
    assert desconto.memo == "Código: 0926 | Quantidade: 22,5"
    assert f"{desconto.amount:.2f}" == "-175.31"

    liquido = statement.transactions[-1]
    assert liquido.name == "Valor Líquido Depositado"
    assert f"{liquido.amount:.2f}" == "-8503.02"


def test_process_pdf_generates_bank_ofx_from_real_pb_sample(tmp_path: Path):
    sample_file = Path("samples-local/pb/09746219-202507-Contracheque do M#s.pdf")
    if not sample_file.exists():
        return

    output_path = tmp_path / "pb.ofx"
    process_pdf(sample_file, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "OFXHEADER:100" in content
    assert "<BANKMSGSRSV1>" in content
    assert "<BANKID>PB" in content
    assert "<ACCTID>" in content
    assert "<DTSTART>20250725000000" in content
    assert "<DTEND>20250725000000" in content
    assert "<NAME>Salário Básico" in content
    assert "<MEMO>Código: 0927 | Quantidade: 27,5" in content
    assert "<TRNAMT>8797.61" in content
    assert "<TRNAMT>-3897.79" in content
    assert "<TRNAMT>-8503.02" in content
