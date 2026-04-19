import argparse
from datetime import datetime
from pathlib import Path
import re

from pypdf import PdfReader

from statement_converter._ofx_common import (
    StatementData,
    StatementTransaction,
    build_ofx,
    parse_brl_amount,
)


DATE_HEADER_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
PERIOD_PATTERN = re.compile(r"(\d{2}/\d{2}/\d{2,4})\s*-\s*(\d{2}/\d{2}/\d{2,4})")
ACCOUNT_ID_PATTERN = re.compile(r"Conta\s+([0-9.\-]+)")
TRANSACTION_PATTERN = re.compile(
    r"^(?P<kind>Débito|Crédito)\s+(?P<memo>.+?)\s+(?P<amount>-?[\d.]+,\d{2})\s+(?P<balance>[\d.]+,\d{2})$"
)


def normalize_lines(text: str) -> list[str]:
    return [line.replace("\xa0", " ").strip() for line in text.splitlines() if line.strip()]


def extract_pdf_text(input_path: str | Path) -> str:
    reader = PdfReader(str(input_path))
    if reader.is_encrypted:
        reader.decrypt("")
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def parse_br_date(date_text: str) -> datetime:
    fmt = "%d/%m/%Y" if len(date_text.rsplit("/", 1)[-1]) == 4 else "%d/%m/%y"
    return datetime.strptime(date_text, fmt)


def parse_account_id(text: str) -> str:
    match = ACCOUNT_ID_PATTERN.search(text)
    return match.group(1) if match else "RICO"


def parse_period(text: str) -> tuple[datetime | None, datetime | None]:
    match = PERIOD_PATTERN.search(text)
    if not match:
        return None, None
    return parse_br_date(match.group(1)), parse_br_date(match.group(2))


def normalize_amount(kind: str, raw_amount: str):
    amount = parse_brl_amount(raw_amount)
    if kind == "Débito" and amount > 0:
        return -amount
    if kind == "Crédito" and amount < 0:
        return -amount
    return amount


def parse_statement_text(text: str) -> StatementData:
    lines = normalize_lines(text)
    start_date, end_date = parse_period(text)
    transactions: list[StatementTransaction] = []
    current_date: datetime | None = None

    for line in lines:
        if line.startswith("Saldo disponível"):
            continue

        if DATE_HEADER_PATTERN.match(line):
            current_date = parse_br_date(line)
            continue

        match = TRANSACTION_PATTERN.match(line)
        if not match or current_date is None:
            continue

        transactions.append(
            StatementTransaction(
                posted_at=current_date,
                memo=match.group("memo"),
                amount=normalize_amount(match.group("kind"), match.group("amount")),
                balance=parse_brl_amount(match.group("balance")),
                name=match.group("memo"),
            )
        )

    if not transactions:
        raise ValueError("No transactions were found in the Rico old-account PDF.")

    transactions.sort(key=lambda transaction: transaction.posted_at)

    return StatementData(
        account_id=parse_account_id(text),
        account_type="CHECKING",
        bank_id="RICO",
        currency="BRL",
        generated_at=None,
        start_date=start_date,
        end_date=end_date,
        transactions=transactions,
    )


def parse_pdf(input_path: str | Path) -> StatementData:
    return parse_statement_text(extract_pdf_text(input_path))


def process_pdf(input_path: str | Path, output_path: str | Path) -> None:
    statement = parse_pdf(input_path)
    Path(output_path).write_text(build_ofx(statement), encoding="utf-8")
    print(f"OFX successfully generated: {output_path} ({len(statement.transactions)} transactions)")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a Rico Conta Antiga PDF into an OFX file.")
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
        model="rico-antigo",
        description="Rico Conta Antiga PDF para OFX",
        aliases=("rico-antigo-pdf-ofx",),
    )(_run)


if __name__ == "__main__":
    main()
