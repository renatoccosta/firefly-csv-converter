import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from firefly_csv_converter._ofx_common import StatementData, StatementTransaction, build_ofx


DATETIME_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")
STREAM_PATTERN = re.compile(r"(\d+) 0 obj\s*<<\s*/Length .*?>>\s*stream\n(.*?)\nendstream", re.S)
TEXT_BLOCK_PATTERN = re.compile(r"(?ms)^[ \t]*BT\s*$\n(.*?)^[ \t]*ET\s*$")


def unescape_pdf_string(raw: str) -> str:
    return raw.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")


def extract_pages(pdf_text: str) -> list[list[tuple[float, float, str]]]:
    pages: list[list[tuple[float, float, str]]] = []

    for stream_match in STREAM_PATTERN.finditer(pdf_text):
        stream_text = stream_match.group(2)
        page_elements: list[tuple[float, float, str]] = []

        for block_match in TEXT_BLOCK_PATTERN.finditer(stream_text):
            block = block_match.group(1)
            position_match = re.search(r"([\-0-9.]+) ([\-0-9.]+) Td", block)
            text_match = re.search(r"\((.*?)\)\s*Tj", block, re.S)
            if not (position_match and text_match):
                continue

            text = unescape_pdf_string(text_match.group(1)).strip()
            if text:
                page_elements.append((float(position_match.group(2)), float(position_match.group(1)), text))

        if any(text == "Data da Operação" for _, _, text in page_elements):
            pages.append(page_elements)

    return pages


def parse_ifood_amount(value_text: str) -> Decimal:
    cleaned = value_text.replace("R$", "").replace(" ", "").replace(",", "")
    if "." in cleaned:
        cleaned = cleaned.replace(".", "")
        return Decimal(cleaned) / Decimal("100")
    return Decimal(cleaned)


def parse_transactions(pages: list[list[tuple[float, float, str]]]) -> list[StatementTransaction]:
    transactions: list[StatementTransaction] = []
    for elements in pages:
        rows: dict[float, list[tuple[float, str]]] = {}

        for y, x, text in elements:
            rows.setdefault(y, []).append((x, text))

        for y in sorted(rows.keys(), reverse=True):
            cells = sorted(rows[y], key=lambda item: item[0])
            datetime_text = next((text for x, text in cells if x < 120 and DATETIME_PATTERN.match(text)), None)
            if not datetime_text:
                continue

            name = next((text for x, text in cells if 130 <= x < 320), None)
            value_text = next((text for x, text in cells if 320 <= x < 410 and "R$" in text), None)
            memo = next((text for x, text in cells if x >= 480), "")

            if not (name and value_text):
                continue

            transactions.append(
                StatementTransaction(
                    posted_at=datetime.strptime(datetime_text, "%d/%m/%Y %H:%M:%S"),
                    name=name,
                    memo=memo,
                    amount=parse_ifood_amount(value_text),
                    balance=None,
                )
            )

    return sorted(transactions, key=lambda transaction: transaction.posted_at)


def parse_pdf(input_path: str | Path) -> StatementData:
    pdf_text = Path(input_path).read_text(encoding="latin1")
    pages = extract_pages(pdf_text)
    transactions = parse_transactions(pages)

    return StatementData(
        account_id="IFOOD",
        account_type="CHECKING",
        bank_id="IFOOD",
        currency="BRL",
        generated_at=None,
        start_date=None,
        end_date=None,
        transactions=transactions,
    )


def process_pdf(input_path: str | Path, output_path: str | Path) -> None:
    statement = parse_pdf(input_path)
    Path(output_path).write_text(build_ofx(statement), encoding="utf-8")
    print(f"OFX successfully generated: {output_path} ({len(statement.transactions)} transactions)")


def main() -> None:
    if len(sys.argv) < 3:
        script_name = Path(sys.argv[0]).name
        print(f"Usage: {script_name} <input.pdf> <output.ofx>")
        sys.exit(1)

    process_pdf(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
