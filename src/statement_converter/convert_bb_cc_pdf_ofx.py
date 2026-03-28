import argparse
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader
from pypdf._page import PageObject
from pypdf.generic import ContentStream

from statement_converter._ofx_common import (
    StatementData,
    StatementTransaction,
    build_ofx,
    parse_brl_amount,
    parse_datetime_br,
)


DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
ACCOUNT_ID_PATTERN = re.compile(r"Conta:\s*([0-9A-Z.-]+)")
GENERATED_AT_PATTERN = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*Autoatendimento BB\s*-\s*(\d{2}:\d{2}:\d{2})")
AMOUNT_TEXT_PATTERN = re.compile(r"([\d.]+,\d{2})")
BLUE_RGB = (0.0, 0.53333, 0.73333)
RED_RGB = (1.0, 0.0, 0.03922)


@dataclass(frozen=True)
class TextElement:
    x: float
    y: float
    text: str
    color: tuple[float, float, float] | None


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def is_balance_label(value: str) -> bool:
    compact = re.sub(r"[^A-Za-z]", "", normalize_text(value)).casefold()
    return compact in {"saldo", "saldoanterior"}


def is_close_color(actual: tuple[float, float, float] | None, expected: tuple[float, float, float], tolerance: float = 0.05) -> bool:
    if actual is None:
        return False
    return all(abs(component - target) <= tolerance for component, target in zip(actual, expected, strict=True))


def classify_amount_sign(amount_text: str, color: tuple[float, float, float] | None) -> int:
    if is_close_color(color, BLUE_RGB):
        return 1
    if is_close_color(color, RED_RGB):
        return -1
    if amount_text.endswith(" C"):
        return 1
    if amount_text.endswith(" D"):
        return -1
    raise ValueError(f"Não foi possível identificar débito/crédito para o valor: {amount_text}")


def clean_text(value: str) -> str:
    return value.replace("€", " ").strip()


def extract_page_elements(page: PageObject, reader: PdfReader) -> list[TextElement]:
    content_stream = ContentStream(page.get_contents(), reader)
    elements: list[TextElement] = []
    current_color: tuple[float, float, float] | None = None
    current_tm: tuple[float, float, float, float, float, float] | None = None

    for operands, operator in content_stream.operations:
        if operator == b"rg":
            current_color = tuple(float(value) for value in operands)
            continue

        if operator == b"Tm":
            current_tm = tuple(float(value) for value in operands)
            continue

        if operator != b"Tj" or current_tm is None:
            continue

        text = clean_text(str(operands[0]))
        if not text:
            continue

        elements.append(
            TextElement(
                x=current_tm[4],
                y=current_tm[5],
                text=text,
                color=current_color,
            )
        )

    return elements


def extract_pdf_elements(input_path: str | Path) -> list[list[TextElement]]:
    reader = PdfReader(str(input_path))
    if reader.is_encrypted:
        reader.decrypt("")
    return [extract_page_elements(page, reader) for page in reader.pages]


def parse_account_id(pages: list[list[TextElement]]) -> str:
    for page in pages:
        joined_text = " ".join(element.text for element in page)
        match = ACCOUNT_ID_PATTERN.search(joined_text)
        if match:
            return match.group(1)
    raise ValueError("Não foi possível identificar a conta no PDF do Banco do Brasil.")


def parse_generated_at(pages: list[list[TextElement]]):
    for page in pages:
        for element in page:
            match = GENERATED_AT_PATTERN.search(element.text)
            if match:
                return parse_datetime_br(match.group(1), match.group(2))
    return None


def column_elements(elements: list[TextElement], start_x: float, end_x: float | None = None) -> list[TextElement]:
    return [
        element
        for element in elements
        if element.x >= start_x and (end_x is None or element.x < end_x)
    ]


def join_column_text(elements: list[TextElement]) -> str:
    ordered = sorted(elements, key=lambda element: (-element.y, element.x))
    return " ".join(element.text for element in ordered if element.text).strip()


def build_row_memo(dep_origin: str, document: str, history_lines: list[str]) -> str:
    parts = [part for part in [dep_origin, document, *history_lines[1:]] if part]
    return " | ".join(parts)


def parse_row_transaction(date_element: TextElement, row_elements: list[TextElement]) -> StatementTransaction | None:
    dep_origin = join_column_text(column_elements(row_elements, 100, 160))
    history_column = column_elements(row_elements, 160, 303)
    history_lines = [element.text for element in sorted(history_column, key=lambda element: (-element.y, element.x))]
    document = join_column_text(column_elements(row_elements, 303, 405))
    value_elements = sorted(column_elements(row_elements, 405, 470), key=lambda element: (-element.y, element.x))

    if not history_lines or not value_elements:
        return None

    if is_balance_label(history_lines[0]):
        return None

    amount_element = value_elements[0]
    amount_match = AMOUNT_TEXT_PATTERN.search(amount_element.text)
    if not amount_match:
        raise ValueError(f"Valor não reconhecido no PDF do Banco do Brasil: {amount_element.text}")

    amount = parse_brl_amount(amount_match.group(1))
    sign = classify_amount_sign(amount_element.text, amount_element.color)

    return StatementTransaction(
        posted_at=parse_datetime_br(date_element.text),
        name=history_lines[0],
        memo=build_row_memo(dep_origin, document, history_lines),
        amount=amount if sign > 0 else -amount,
        balance=None,
    )


def parse_page_transactions(elements: list[TextElement]) -> list[StatementTransaction]:
    date_elements = sorted(
        [
            element
            for element in elements
            if element.x < 100 and DATE_PATTERN.match(element.text) and element.y < 760
        ],
        key=lambda element: -element.y,
    )
    transactions: list[StatementTransaction] = []

    for index, date_element in enumerate(date_elements):
        upper_bound = date_element.y + 13 if index == 0 else (date_elements[index - 1].y + date_element.y) / 2
        lower_bound = date_element.y - 13 if index == len(date_elements) - 1 else (date_element.y + date_elements[index + 1].y) / 2
        row_elements = [
            element
            for element in elements
            if lower_bound < element.y <= upper_bound and 40 <= element.y < 760 and element.x < 470
        ]
        transaction = parse_row_transaction(date_element, row_elements)
        if transaction is not None:
            transactions.append(transaction)

    return transactions


def parse_elements(pages: list[list[TextElement]]) -> StatementData:
    transactions: list[StatementTransaction] = []
    for page in pages:
        transactions.extend(parse_page_transactions(page))

    return StatementData(
        account_id=parse_account_id(pages),
        account_type="CHECKING",
        bank_id="001",
        currency="BRL",
        generated_at=parse_generated_at(pages),
        start_date=None,
        end_date=None,
        transactions=transactions,
    )


def parse_pdf(input_path: str | Path) -> StatementData:
    return parse_elements(extract_pdf_elements(input_path))


def process_pdf(input_path: str | Path, output_path: str | Path) -> None:
    statement = parse_pdf(input_path)
    Path(output_path).write_text(build_ofx(statement), encoding="utf-8")
    print(f"OFX successfully generated: {output_path} ({len(statement.transactions)} transactions)")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a Banco do Brasil checking-account PDF statement into OFX.")
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
        model="bb-cc",
        description="BB conta corrente PDF para OFX",
        aliases=("bb-pdf-ofx", "bb-cc-pdf-ofx"),
    )(_run)


if __name__ == "__main__":
    main()
