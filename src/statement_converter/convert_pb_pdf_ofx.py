import argparse
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

from statement_converter._ofx_common import (
    StatementData,
    StatementTransaction,
    build_ofx,
    parse_brl_amount,
    parse_datetime_br,
)


DATE_PATTERN = re.compile(r"(\d{2}/\d{2}/\d{4})\s+Disponível\b")
ACCOUNT_ID_PATTERN = re.compile(r"(\d+)\s+Matrícula\b")
NET_DEPOSIT_PATTERN = re.compile(r"R\$\s*([\d.]+,\d{2})\s+Valor Líquido Depositado\b", re.IGNORECASE)
ROW_PATTERN = re.compile(r"^(?P<code>[0-9A-Z]{4})\s+(?P<body>.+?)\s+R\$\s*(?P<amount>[\d.]+,\d{2})$")
QUANTITY_PATTERN = re.compile(r"^\d+(?:,\d+)?$")


@dataclass(frozen=True)
class ParsedRow:
    code: str
    description: str
    quantity: str | None
    amount: Decimal


def normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_pdf_text(input_path: str | Path) -> str:
    reader = PdfReader(str(input_path))
    if reader.is_encrypted:
        reader.decrypt("")
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def parse_posted_at(text: str):
    match = DATE_PATTERN.search(text)
    if not match:
        raise ValueError("Não foi possível localizar a data em 'Disponível' no PDF da PB.")
    return parse_datetime_br(match.group(1))


def parse_account_id(text: str) -> str:
    match = ACCOUNT_ID_PATTERN.search(text)
    return match.group(1) if match else "PB"


def parse_net_deposit_amount(text: str) -> Decimal:
    match = NET_DEPOSIT_PATTERN.search(text)
    if not match:
        raise ValueError("Não foi possível localizar o valor em 'Valor Líquido Depositado' no PDF da PB.")
    return parse_brl_amount(match.group(1))


def parse_row(line: str) -> ParsedRow | None:
    match = ROW_PATTERN.match(line)
    if not match:
        return None

    body = match.group("body").strip()
    tokens = body.split()
    quantity = None
    if len(tokens) >= 2 and QUANTITY_PATTERN.match(tokens[-1]):
        quantity = tokens[-1]
        description = " ".join(tokens[:-1]).strip()
    else:
        description = body

    if not description:
        raise ValueError(f"Linha sem descrição reconhecível no PDF da PB: {line}")

    return ParsedRow(
        code=match.group("code"),
        description=description,
        quantity=quantity,
        amount=parse_brl_amount(match.group("amount")),
    )


def build_row_memo(row: ParsedRow) -> str:
    parts = [f"Código: {row.code}"]
    if row.quantity:
        parts.append(f"Quantidade: {row.quantity}")
    return " | ".join(parts)


def build_row_transaction(row: ParsedRow, posted_at, sign: int) -> StatementTransaction:
    return StatementTransaction(
        posted_at=posted_at,
        name=row.description,
        memo=build_row_memo(row),
        amount=row.amount if sign > 0 else -row.amount,
        balance=None,
    )


def parse_table_transactions(lines: list[str], posted_at) -> list[StatementTransaction]:
    transactions: list[StatementTransaction] = []
    buffered_rows: list[ParsedRow] = []
    in_table = False

    for line in lines:
        if not in_table:
            if line == "Código Descrição Quantidade Valor":
                in_table = True
            continue

        if "Total de Proventos" in line:
            transactions.extend(build_row_transaction(row, posted_at, 1) for row in buffered_rows)
            buffered_rows = []
            continue

        if "Total de Descontos" in line:
            transactions.extend(build_row_transaction(row, posted_at, -1) for row in buffered_rows)
            buffered_rows = []
            continue

        if line == "Total Líquido":
            break

        row = parse_row(line)
        if row is not None:
            buffered_rows.append(row)

    if buffered_rows:
        raise ValueError("Foram encontradas linhas da tabela da PB sem totalizador correspondente.")

    return transactions


def parse_statement_text(text: str) -> StatementData:
    posted_at = parse_posted_at(text)
    lines = normalize_lines(text)
    transactions = parse_table_transactions(lines, posted_at)
    transactions.append(
        StatementTransaction(
            posted_at=posted_at,
            name="Valor Líquido Depositado",
            memo="Resumo do contracheque PB",
            amount=-parse_net_deposit_amount(text),
            balance=None,
        )
    )

    return StatementData(
        account_id=parse_account_id(text),
        account_type="CHECKING",
        bank_id="PB",
        currency="BRL",
        generated_at=None,
        start_date=None,
        end_date=None,
        transactions=transactions,
    )


def parse_pdf(input_path: str | Path) -> StatementData:
    return parse_statement_text(extract_pdf_text(input_path))


def process_pdf(input_path: str | Path, output_path: str | Path) -> None:
    statement = parse_pdf(input_path)
    Path(output_path).write_text(build_ofx(statement), encoding="utf-8")
    print(f"OFX successfully generated: {output_path} ({len(statement.transactions)} transactions)")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a PB payroll PDF into a bank-statement OFX file.")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("output_path", type=Path)
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    process_pdf(args.input_path, args.output_path)


def _run(args: argparse.Namespace) -> None:
    process_pdf(args.input_path, args.output_path)


def register_converters(registry) -> None:
    registry.register(
        input_format="pdf",
        output_format="ofx",
        model="pb",
        description="PB contracheque PDF para OFX",
    )(_run)


if __name__ == "__main__":
    main()
