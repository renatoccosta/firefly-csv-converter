import argparse
import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from firefly_csv_converter._ofx_common import (
    StatementData,
    StatementTransaction,
    build_credit_card_ofx,
)


DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


def parse_due_date(value: str) -> datetime:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    raise ValueError("Due date must be in YYYY-MM-DD or DD/MM/YYYY format.")


def parse_amount(value: str) -> Decimal:
    return Decimal(value.strip().replace(",", "."))


def normalize_description(value: str) -> str:
    return value.strip().strip('"').strip()


def build_memo(row: dict[str, str]) -> str:
    parts = []

    parcela = row["Parcela"].strip()
    if parcela:
        parts.append(f"Parcela: {parcela}")

    final_cartao = row["Final do Cartão"].strip()
    if final_cartao:
        parts.append(f"Cartão: {final_cartao}")

    return " | ".join(parts) or "Fatura C6"


def transaction_amount(description: str, amount: Decimal) -> Decimal:
    if "pagamento" in description.casefold():
        return abs(amount)
    return -abs(amount)


def parse_csv(input_path: str | Path) -> StatementData:
    transactions: list[StatementTransaction] = []
    card_suffixes: set[str] = set()

    with Path(input_path).open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")
        for row in reader:
            description = normalize_description(row["Descrição"])
            amount = parse_amount(row["Valor (em R$)"])
            posted_at = datetime.strptime(row["Data de Compra"].strip(), "%d/%m/%Y")

            card_suffix = row["Final do Cartão"].strip()
            if card_suffix:
                card_suffixes.add(card_suffix)

            transactions.append(
                StatementTransaction(
                    posted_at=posted_at,
                    memo=build_memo(row),
                    amount=transaction_amount(description, amount),
                    balance=None,
                    name=description,
                )
            )

    if not transactions:
        raise ValueError("No transactions were found in the C6 credit card CSV.")

    account_id = "-".join(sorted(card_suffixes)) if card_suffixes else "C6-CREDIT"

    return StatementData(
        account_id=account_id,
        account_type="CREDITCARD",
        bank_id="C6",
        currency="BRL",
        generated_at=None,
        start_date=None,
        end_date=None,
        transactions=sorted(transactions, key=lambda transaction: transaction.posted_at),
    )


def process_csv(input_path: str | Path, output_path: str | Path, due_date: str | datetime) -> None:
    statement = parse_csv(input_path)
    parsed_due_date = parse_due_date(due_date) if isinstance(due_date, str) else due_date
    Path(output_path).write_text(build_credit_card_ofx(statement, parsed_due_date), encoding="utf-8")
    print(f"OFX successfully generated: {output_path} ({len(statement.transactions)} transactions)")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a C6 credit card CSV statement into an OFX credit card statement."
    )
    parser.add_argument("input_path", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--due-date", required=True, help="Statement due date in YYYY-MM-DD or DD/MM/YYYY format.")
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    process_csv(args.input_path, args.output_path, args.due_date)


def _run(args: argparse.Namespace) -> None:
    process_csv(args.input_path, args.output_path, args.due_date)


def register_converters(registry) -> None:
    registry.register(
        input_format="csv",
        output_format="ofx",
        model="c6-credit-csv",
        description="C6 cartao de credito CSV para OFX",
        aliases=("c6-csv",),
        required_options=("due_date",),
    )(_run)


if __name__ == "__main__":
    main()
