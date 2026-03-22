import argparse
import sys
from datetime import datetime
from pathlib import Path

from firefly_csv_converter._ofx_common import StatementData, StatementTransaction, build_ofx
from firefly_csv_converter._rico_cc_common import RicoStatementRow, parse_statement


def _posted_at(row: RicoStatementRow) -> datetime:
    base_date = row.liquidacao or row.movimentacao
    if base_date is None:
        raise ValueError(f"Transaction without date in Rico spreadsheet: {row.lancamento}")
    return datetime.combine(base_date, datetime.min.time())


def parse_input(input_path: str | Path) -> StatementData:
    statement = parse_statement(input_path)

    transactions = [
        StatementTransaction(
            posted_at=_posted_at(row),
            memo=row.lancamento,
            amount=row.valor,
            balance=row.saldo,
        )
        for row in statement.rows
        if row.valor is not None
    ]

    if not transactions:
        raise ValueError("No transactions were found in the Rico spreadsheet.")

    return StatementData(
        account_id=statement.account_id or "RICO",
        account_type="CHECKING",
        bank_id="RICO",
        currency="BRL",
        generated_at=statement.generated_at,
        start_date=None,
        end_date=None,
        transactions=transactions,
    )


def process_ofx(input_path: str | Path, output_path: str | Path) -> None:
    statement = parse_input(input_path)
    Path(output_path).write_text(build_ofx(statement), encoding="utf-8")
    print(f"OFX successfully generated: {output_path} ({len(statement.transactions)} transactions)")


def main() -> None:
    if len(sys.argv) < 3:
        script_name = Path(sys.argv[0]).name
        print(f"Usage: {script_name} <input.xlsx> <output.ofx>")
        sys.exit(1)

    process_ofx(Path(sys.argv[1]), Path(sys.argv[2]))


def _run(args: argparse.Namespace) -> None:
    process_ofx(args.input_path, args.output_path)


def register_converters(registry) -> None:
    registry.register(
        input_format="xlsx",
        output_format="ofx",
        model="rico",
        description="Rico XLSX para OFX",
    )(_run)


if __name__ == "__main__":
    main()
