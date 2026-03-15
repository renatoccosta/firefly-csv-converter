import re
import sys
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from firefly_csv_converter._ofx_common import (
    StatementData,
    StatementTransaction,
    build_ofx,
    parse_brl_amount,
    parse_datetime_br,
)


DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}$")
PAGE_PATTERN = re.compile(r"^\d+ de \d+$")
STREAM_PATTERN = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
TEXT_PATTERN = re.compile(
    rb"([\-0-9.]+)\s+([\-0-9.]+)\s+Td\s+\((.*?)\)\s+Tj",
    re.S,
)


@dataclass(frozen=True)
class PdfTextElement:
    x: float
    y: float
    text: str


def decode_pdf_string(raw: bytes) -> str:
    normalized = raw.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
    if b"\x00" in normalized:
        text = normalized.decode("utf-16-be", "replace")
    else:
        text = normalized.decode("latin1", "replace")
    return text.replace("\x0b", " ").replace("\u200b", "").strip()


def extract_text_elements(pdf_bytes: bytes) -> list[list[PdfTextElement]]:
    pages: list[list[PdfTextElement]] = []

    for stream_match in STREAM_PATTERN.finditer(pdf_bytes):
        raw_stream = stream_match.group(1)
        try:
            stream = zlib.decompress(raw_stream)
        except zlib.error:
            continue

        page_elements: list[PdfTextElement] = []
        for text_match in TEXT_PATTERN.finditer(stream):
            x = float(text_match.group(1))
            y = float(text_match.group(2))
            text = decode_pdf_string(text_match.group(3))
            if text:
                page_elements.append(PdfTextElement(x=x, y=y, text=text))

        if any(element.text == "MOVIMENTAÇÕES" for element in page_elements):
            pages.append(page_elements)

    return pages


def parse_period(text: str) -> tuple[datetime | None, datetime | None]:
    match = re.search(
        r"(\d{1,2}) DE ([A-ZÇ]+) DE (\d{4}) A (\d{1,2}) DE ([A-ZÇ]+) DE (\d{4})",
        text,
    )
    if not match:
        return None, None

    months = {
        "JANEIRO": 1,
        "FEVEREIRO": 2,
        "MARCO": 3,
        "MARÇO": 3,
        "ABRIL": 4,
        "MAIO": 5,
        "JUNHO": 6,
        "JULHO": 7,
        "AGOSTO": 8,
        "SETEMBRO": 9,
        "OUTUBRO": 10,
        "NOVEMBRO": 11,
        "DEZEMBRO": 12,
    }

    start = datetime(int(match.group(3)), months[match.group(2)], int(match.group(1)))
    end = datetime(int(match.group(6)), months[match.group(5)], int(match.group(4)))
    return start, end


def parse_generated_at(text: str) -> datetime | None:
    match = re.search(r"(\d{2}/\d{2}/\d{4}) às (\d{2}:\d{2}:\d{2})", text)
    if not match:
        return None
    return parse_datetime_br(match.group(1), match.group(2))


def extract_statement_metadata(pages: list[list[PdfTextElement]]) -> StatementData:
    if not pages:
        raise ValueError("Nenhuma página de extrato PicPay foi identificada no PDF.")

    account_id = ""
    generated_at = None
    start_date = None
    end_date = None

    for element in pages[0]:
        if element.text == "Conta:":
            continue
        if DATE_PATTERN.match(element.text):
            continue
        if element.text.isdigit() and len(element.text) >= 6 and not account_id:
            previous_texts = [item.text for item in pages[0]]
            index = previous_texts.index(element.text)
            if index > 0 and previous_texts[index - 1] == "Conta:":
                account_id = element.text
        if element.text.startswith("Extrato gerado em "):
            generated_at = parse_generated_at(element.text)
        if " DE " in element.text and " A " in element.text and "JANEIRO" in element.text:
            start_date, end_date = parse_period(element.text)

    if not account_id:
        raise ValueError("Não foi possível identificar o número da conta no PDF.")

    return StatementData(
        account_id=account_id,
        account_type="CHECKING",
        bank_id="PICPAY",
        currency="BRL",
        generated_at=generated_at,
        start_date=start_date,
        end_date=end_date,
        transactions=[],
    )


def parse_transactions_from_page(page_elements: list[PdfTextElement]) -> list[StatementTransaction]:
    transactions: list[StatementTransaction] = []
    index = 0

    while index < len(page_elements):
        element = page_elements[index]

        if not DATE_PATTERN.match(element.text):
            index += 1
            continue

        if index + 3 >= len(page_elements):
            break

        date_text = element.text
        time_element = page_elements[index + 1]
        description_element = page_elements[index + 2]
        amount_element = page_elements[index + 3]

        if not TIME_PATTERN.match(time_element.text):
            index += 1
            continue

        if DATE_PATTERN.match(description_element.text) or PAGE_PATTERN.match(description_element.text):
            index += 1
            continue

        if "R$" not in amount_element.text:
            index += 1
            continue

        balance = None
        next_index = index + 4
        if next_index < len(page_elements) and "R$" in page_elements[next_index].text:
            balance = parse_brl_amount(page_elements[next_index].text)
            next_index += 1
            if next_index < len(page_elements) and "R$" in page_elements[next_index].text:
                next_index += 1
        else:
            while next_index < len(page_elements) and page_elements[next_index].text == "-":
                next_index += 1

        transactions.append(
            StatementTransaction(
                posted_at=parse_datetime_br(date_text, time_element.text),
                memo=description_element.text,
                amount=parse_brl_amount(amount_element.text),
                balance=balance,
            )
        )
        index = next_index

    return transactions


def parse_pdf(input_path: str | Path) -> StatementData:
    pdf_bytes = Path(input_path).read_bytes()
    pages = extract_text_elements(pdf_bytes)
    statement = extract_statement_metadata(pages)

    transactions: list[StatementTransaction] = []
    for page in pages:
        transactions.extend(parse_transactions_from_page(page))

    return StatementData(
        account_id=statement.account_id,
        account_type=statement.account_type,
        bank_id=statement.bank_id,
        currency=statement.currency,
        generated_at=statement.generated_at,
        start_date=statement.start_date,
        end_date=statement.end_date,
        transactions=transactions,
    )


def process_pdf(input_path: str | Path, output_path: str | Path) -> None:
    statement = parse_pdf(input_path)
    ofx_content = build_ofx(statement)
    Path(output_path).write_text(ofx_content, encoding="utf-8")
    print(f"OFX successfully generated: {output_path} ({len(statement.transactions)} transactions)")


def main() -> None:
    if len(sys.argv) < 3:
        script_name = Path(sys.argv[0]).name
        print(f"Usage: {script_name} <input.pdf> <output.ofx>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    process_pdf(input_file, output_file)


if __name__ == "__main__":
    main()
