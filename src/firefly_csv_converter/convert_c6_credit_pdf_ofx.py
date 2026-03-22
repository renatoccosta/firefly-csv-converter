import argparse
import re
import zlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from firefly_csv_converter._ofx_common import (
    StatementData,
    StatementTransaction,
    build_credit_card_ofx,
)


DATE_PATTERN = re.compile(r"^\s*(\d{1,2}) ([a-z]{3})\s*$", re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r"^\d[\d.]*,\d{2}$")
REFERENCE_DATE_PATTERN = re.compile(
    r"Lembrando: nesta fatura serão lançadas apenas transações feitas até (\d{2}/\d{2}/\d{2})\.",
    re.IGNORECASE,
)
PARCEL_PATTERN = re.compile(r"\bparcela\s+(\d+)/(\d+)\b", re.IGNORECASE)
PAYMENT_PATTERN = re.compile(r"inclus[aã]o de pagamento", re.IGNORECASE)
ESTORNO_PATTERN = re.compile(r"\bestorno\b", re.IGNORECASE)
CARD_SUFFIX_PATTERN = re.compile(r"Final (\d{4})")


SHORT_MONTHS = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}

LONG_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


@dataclass(frozen=True)
class PdfTextElement:
    x: float
    y: float
    text: str
    color: tuple[float, float, float] | None


def unescape_pdf_string(raw: bytes) -> bytes:
    out = bytearray()
    index = 0

    while index < len(raw):
        if raw[index] == 92 and index + 1 < len(raw) and raw[index + 1] in b"\\()":
            out.append(raw[index + 1])
            index += 2
            continue
        out.append(raw[index])
        index += 1

    return bytes(out)


def decode_text_block(block: bytes) -> str:
    parts: list[str] = []

    for match in re.finditer(rb"\[(.*?)\]\s*TJ|\((.*?)\)\s*Tj", block, re.S):
        if match.group(1) is not None:
            parts.extend(
                unescape_pdf_string(item).decode("latin1", "replace")
                for item in re.findall(rb"\((.*?)\)", match.group(1), re.S)
            )
            continue

        if match.group(2) is not None:
            parts.append(unescape_pdf_string(match.group(2)).decode("latin1", "replace"))

    return "".join(parts).strip()


def parse_fill_color(block: bytes) -> tuple[float, float, float] | None:
    matches = re.findall(rb"([0-9.]+) ([0-9.]+) ([0-9.]+) rg", block)
    if not matches:
        return None
    red, green, blue = matches[-1]
    return (float(red), float(green), float(blue))


def extract_text_elements(pdf_bytes: bytes) -> list[list[PdfTextElement]]:
    pages: list[list[PdfTextElement]] = []

    for stream_match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        raw_stream = stream_match.group(1)
        try:
            stream = zlib.decompress(raw_stream)
        except zlib.error:
            continue

        page_elements: list[PdfTextElement] = []
        for block_match in re.finditer(rb"BT\s*(.*?)\s*ET", stream, re.S):
            block = block_match.group(1)
            position_match = re.search(rb"1 0 0 1 ([\-0-9.]+) ([\-0-9.]+) Tm", block)
            if not position_match:
                continue

            text = decode_text_block(block)
            if not text:
                continue

            page_elements.append(
                PdfTextElement(
                    x=float(position_match.group(1)),
                    y=float(position_match.group(2)),
                    text=text,
                    color=parse_fill_color(block),
                )
            )

        if any("Lembrando: nesta fatura" in element.text for element in page_elements):
            pages.append(page_elements)

    return pages


def subtract_months(year: int, month: int, months: int) -> tuple[int, int]:
    month_index = year * 12 + (month - 1) - months
    return month_index // 12, month_index % 12 + 1


def parse_reference_date(text: str) -> datetime:
    match = REFERENCE_DATE_PATTERN.search(text)
    if not match:
        raise ValueError("Não foi possível identificar a data de referência da fatura do C6.")
    return datetime.strptime(match.group(1), "%d/%m/%y")


def parse_displayed_date(date_text: str) -> tuple[int, int]:
    match = DATE_PATTERN.match(date_text)
    if not match:
        raise ValueError(f"Data abreviada não reconhecida no PDF do C6: {date_text}")
    return int(match.group(1)), SHORT_MONTHS[match.group(2).lower()]


def infer_transaction_year(day: int, month: int, description: str, reference_date: datetime) -> int:
    default_year = reference_date.year - 1 if month > reference_date.month else reference_date.year

    parcel_match = PARCEL_PATTERN.search(description)
    if parcel_match and month <= reference_date.month:
        installment_number = int(parcel_match.group(1))
        inferred_year, _ = subtract_months(default_year, month, installment_number - 1)
        return inferred_year

    return default_year


def parse_transaction_date(date_text: str, description: str, reference_date: datetime) -> datetime:
    day, month = parse_displayed_date(date_text)
    year = infer_transaction_year(day, month, description, reference_date)
    return datetime(year, month, day)


def parse_due_date(text: str, reference_date: datetime) -> datetime:
    match = re.search(r"(\d{1,2}) de ([A-Za-zçÇ]+)", text)
    if not match:
        raise ValueError(f"Data de vencimento não reconhecida no PDF do C6: {text}")

    day = int(match.group(1))
    month = LONG_MONTHS[match.group(2).lower()]
    year = reference_date.year if month >= reference_date.month else reference_date.year + 1
    return datetime(year, month, day)


def is_due_date_text(text: str) -> bool:
    return re.search(r"^\d{1,2} de [A-Za-zçÇ]+$", text.strip()) is not None


def is_credit_transaction(description: str, color: tuple[float, float, float] | None = None) -> bool:
    lowered = description.casefold()
    if PAYMENT_PATTERN.search(lowered) or ESTORNO_PATTERN.search(lowered):
        return True

    if color is None:
        return False

    red, green, blue = color
    return green > red and green > blue


def parse_amount(text: str) -> Decimal:
    return Decimal(text.replace(".", "").replace(",", "."))


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_name(description: str) -> str:
    name = PARCEL_PATTERN.sub("", description)
    name = re.sub(r"\s*-\s*Estorno\b", "", name, flags=re.IGNORECASE)
    return normalize_spaces(name).strip(" -") or normalize_spaces(description)


def build_memo(description: str, card_suffix: str | None) -> str:
    parts = []

    parcel_match = PARCEL_PATTERN.search(description)
    if parcel_match:
        parts.append(f"Parcela: {parcel_match.group(1)}/{parcel_match.group(2)}")

    if ESTORNO_PATTERN.search(description):
        parts.append("Estorno")

    if card_suffix:
        parts.append(f"Cartão: {card_suffix}")

    return " | ".join(parts) or "Fatura C6"


def extract_reference_and_due_date(pages: list[list[PdfTextElement]]) -> tuple[datetime, datetime]:
    reference_date = None
    due_date = None

    for page in pages:
        for element in page:
            if reference_date is None and "Lembrando: nesta fatura" in element.text:
                reference_date = parse_reference_date(element.text)

    for page in pages:
        for element in page:
            if due_date is None and "Vencimento:" in element.text and is_due_date_text(
                element.text.split("Vencimento:", 1)[-1].strip()
            ):
                due_date = parse_due_date(element.text.split("Vencimento:", 1)[-1].strip(), reference_date or datetime.now())
                continue

            if due_date is None and element.text.startswith("Vencimento:"):
                same_line = [
                    candidate
                    for candidate in page
                    if abs(candidate.y - element.y) <= 2 and candidate.x > element.x and is_due_date_text(candidate.text)
                ]
                if same_line:
                    same_line.sort(key=lambda candidate: candidate.x)
                    due_date = parse_due_date(same_line[0].text, reference_date or datetime.now())

    if reference_date is None:
        raise ValueError("Não foi possível localizar a data de corte no PDF do C6.")
    if due_date is None:
        raise ValueError("Não foi possível localizar o vencimento da fatura no PDF do C6.")

    return reference_date, due_date


def parse_transactions(pages: list[list[PdfTextElement]], reference_date: datetime) -> tuple[list[StatementTransaction], set[str]]:
    transactions: list[StatementTransaction] = []
    card_suffixes: set[str] = set()

    for page in pages:
        rows: dict[float, list[PdfTextElement]] = {}
        for element in page:
            rows.setdefault(round(element.y, 1), []).append(element)

        current_card_suffix: str | None = None
        for y in sorted(rows.keys(), reverse=True):
            cells = sorted(rows[y], key=lambda item: item.x)
            row_text = normalize_spaces(" ".join(cell.text for cell in cells))

            card_match = CARD_SUFFIX_PATTERN.search(row_text)
            if card_match:
                current_card_suffix = card_match.group(1)
                card_suffixes.add(current_card_suffix)
                continue

            date_cell = next((cell for cell in cells if cell.x <= 80 and DATE_PATTERN.match(cell.text)), None)
            amount_cell = next((cell for cell in reversed(cells) if cell.x >= 500 and AMOUNT_PATTERN.match(cell.text)), None)
            if not date_cell or not amount_cell:
                continue

            description_parts = [
                normalize_spaces(cell.text)
                for cell in cells
                if 90 <= cell.x < 500 and "Subtotal deste cartão" not in cell.text
            ]
            description = normalize_spaces(" ".join(part for part in description_parts if part))
            if not description:
                continue

            amount = parse_amount(amount_cell.text)
            if not is_credit_transaction(description, amount_cell.color):
                amount = -amount

            transactions.append(
                StatementTransaction(
                    posted_at=parse_transaction_date(date_cell.text, description, reference_date),
                    memo=build_memo(description, current_card_suffix),
                    amount=amount,
                    balance=None,
                    name=build_name(description),
                )
            )

    return sorted(transactions, key=lambda transaction: transaction.posted_at), card_suffixes


def parse_pdf_document(input_path: str | Path) -> tuple[StatementData, datetime]:
    pdf_bytes = Path(input_path).read_bytes()
    pages = extract_text_elements(pdf_bytes)
    if not pages:
        raise ValueError("Nenhuma página de fatura C6 foi identificada no PDF.")

    reference_date, due_date = extract_reference_and_due_date(pages)
    transactions, card_suffixes = parse_transactions(pages, reference_date)
    if not transactions:
        raise ValueError("No transactions were found in the C6 credit card PDF.")

    account_id = "-".join(sorted(card_suffixes)) if card_suffixes else "C6-CREDIT"
    statement = StatementData(
        account_id=account_id,
        account_type="CREDITCARD",
        bank_id="C6",
        currency="BRL",
        generated_at=None,
        start_date=None,
        end_date=None,
        transactions=transactions,
    )
    return statement, due_date


def parse_pdf(input_path: str | Path) -> StatementData:
    statement, _ = parse_pdf_document(input_path)
    return statement


def process_pdf(input_path: str | Path, output_path: str | Path) -> None:
    statement, due_date = parse_pdf_document(input_path)
    Path(output_path).write_text(build_credit_card_ofx(statement, due_date), encoding="utf-8")
    print(f"OFX successfully generated: {output_path} ({len(statement.transactions)} transactions)")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a C6 credit card PDF statement into an OFX credit card statement."
    )
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
        model="c6-credit-pdf",
        description="C6 cartao de credito PDF para OFX",
        aliases=("c6-pdf",),
    )(_run)


if __name__ == "__main__":
    main()
