import sys
import csv
from ofxparse import OfxParser
from pathlib import Path

def parse_input(input_path: str | Path) -> list[dict]:
    """
    Parse the OFX input file and return a list of transaction dictionaries.
    Each transaction contains: Date, Payee, Memo, and Amount.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        ofx = OfxParser.parse(f)

    transactions = []
    # ensure account, statement and transactions exist before iterating
    account = getattr(ofx, "account", None)
    statement = getattr(account, "statement", None) if account else None
    transactions_list = getattr(statement, "transactions", None) if statement else None

    if not transactions_list:
        return transactions

    for t in transactions_list:
        transactions.append({
            "Type": t.type or "",
            "Date": t.date.isoformat() if t.date else "",
            "Amount": f"{t.amount:.2f}".replace(".", ","),
            "Id": t.id or "",
            "Memo": t.memo or ""
        })

    return transactions


def process_csv(input_path: str | Path, output_path: str | Path):
    """
    Process the OFX file and generate the corresponding CSV output.
    """
    transactions = parse_input(input_path)

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["Type", "Date", "Amount", "Id", "Memo"]
        # build fieldnames preserving first-seen order using dict.fromkeys
        # fieldnames = list(dict.fromkeys(k for txn in transactions for k in txn.keys()))

        # fieldnames = ["Date", "Payee", "Memo", "Amount"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(transactions)

    print(f"CSV file successfully generated: {output_path}")


def main():
    """Main function to handle command-line arguments."""
    if len(sys.argv) < 3:
        script_name = Path(sys.argv[0]).name
        print(f"Usage: {script_name} <input.csv> <output.csv>")
        sys.exit(1)
    else:
        input_file = Path(sys.argv[1])
        output_file = Path(sys.argv[2])

        process_csv(input_file, output_file)


if __name__ == "__main__":
    main()
