import re
import sys
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from firefly_csv_converter._picpay_ofx_common import (
    StatementData,
    StatementTransaction,
    build_ofx,
    parse_brl_amount,
    parse_datetime_br,
)


TEXT_BLOCK_PATTERN = re.compile(rb"BT\s*(.*?)\s*ET", re.S)
DATE_HEADER_PATTERN = re.compile(r"^\d{1,2} de [a-zç]+(?: de)? \d{4}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
AMOUNT_PATTERN = re.compile(r"^[+\-−]R\$ \d[\d.,]*$")
GENERATED_AT_PATTERN = re.compile(r"(\d{2}/\d{2}/\d{4}) às (\d{2}:\d{2})")


@dataclass(frozen=True)
class PdfTextElement:
    x: float
    y: float
    text: str
    font: str


MONTHS = {
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


def build_font_maps(pdf_bytes: bytes) -> dict[str, dict[int, str]]:
    cmap_streams: list[dict[int, str]] = []

    for stream_match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        raw_stream = stream_match.group(1)
        try:
            stream = zlib.decompress(raw_stream).decode("latin1")
        except Exception:
            continue

        if "begincmap" not in stream:
            continue

        mapping: dict[int, str] = {}
        for line in stream.splitlines():
            match = re.match(r"<([0-9A-Fa-f]+)><([0-9A-Fa-f]+)><([0-9A-Fa-f]+)>", line.strip())
            if not match:
                continue

            start, end, target = [int(value, 16) for value in match.groups()]
            for offset, code in enumerate(range(start, end + 1)):
                mapping[code] = chr(target + offset)

        if mapping:
            cmap_streams.append(mapping)

    if len(cmap_streams) < 2:
        raise ValueError("Não foi possível identificar os mapas de fonte do PDF PicPay 2025.")

    # O layout de 2025 usa duas fontes textuais principais:
    # F2 com mais glifos (valores e conteúdo) e F3 nos títulos/data.
    cmap_streams.sort(key=len, reverse=True)
    return {"F2": cmap_streams[0], "F3": cmap_streams[1]}


def decode_pdf_text(raw: bytes, font: str, font_maps: dict[str, dict[int, str]]) -> str:
    data = unescape_pdf_string(raw)
    chars = []
    font_map = font_maps.get(font, {})

    for index in range(0, len(data), 2):
        code = int.from_bytes(data[index:index + 2], "big")
        chars.append(font_map.get(code, ""))

    return "".join(chars).strip()


def extract_text_elements(pdf_bytes: bytes) -> list[list[PdfTextElement]]:
    font_maps = build_font_maps(pdf_bytes)
    pages: list[list[PdfTextElement]] = []

    for stream_match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        raw_stream = stream_match.group(1)
        try:
            stream = zlib.decompress(raw_stream)
        except zlib.error:
            continue

        page_elements: list[PdfTextElement] = []

        for block_match in TEXT_BLOCK_PATTERN.finditer(stream):
            block = block_match.group(1)
            font_match = re.search(rb"/([A-Za-z0-9]+) [0-9.]+ Tf", block)
            if not font_match:
                continue

            position_match = re.search(rb"1 0 0 1 ([\-0-9.]+) ([\-0-9.]+) Tm", block)
            if not position_match:
                position_match = re.search(rb"([\-0-9.]+) ([\-0-9.]+) Td", block)
            if not position_match:
                continue

            text_match = re.search(rb"\((.*?)\)Tj", block, re.S)
            if not text_match:
                continue

            font = font_match.group(1).decode()
            text = decode_pdf_text(text_match.group(1), font, font_maps)
            if not text:
                continue

            page_elements.append(
                PdfTextElement(
                    x=float(position_match.group(1)),
                    y=float(position_match.group(2)),
                    text=text,
                    font=font,
                )
            )

        has_2025_layout_markers = any(
            element.text == "Extrato de conta"
            or element.text == "Hora"
            or DATE_HEADER_PATTERN.match(element.text)
            for element in page_elements
        )
        if has_2025_layout_markers:
            pages.append(page_elements)

    return pages


def parse_period_lines(page_elements: list[PdfTextElement]) -> tuple[datetime | None, datetime | None]:
    period_lines = [
        element.text
        for element in sorted(page_elements, key=lambda item: (-item.y, item.x))
        if " de " in element.text and "2025" in element.text and element.x < 150
    ]
    if len(period_lines) < 2:
        return None, None

    start_line = period_lines[0].replace(" a", "")
    end_line = period_lines[1]
    return parse_portuguese_date(start_line), parse_portuguese_date(end_line)


def parse_portuguese_date(text: str) -> datetime:
    match = re.match(r"(\d{1,2}) de ([a-zç]+)(?: de)? (\d{4})", text.lower())
    if not match:
        raise ValueError(f"Data em português não reconhecida: {text}")

    day = int(match.group(1))
    month = MONTHS[match.group(2)]
    year = int(match.group(3))
    return datetime(year, month, day)


def extract_statement_metadata(pages: list[list[PdfTextElement]]) -> StatementData:
    if not pages:
        raise ValueError("Nenhuma página do layout PicPay 2025 foi identificada no PDF.")

    first_page = pages[0]
    account_id = ""
    generated_at = None

    for element in first_page:
        if "Conta:" in element.text:
            match = re.search(r"Conta:\s*([0-9-]+)", element.text)
            if match:
                account_id = match.group(1).replace("-", "")
        generated_match = GENERATED_AT_PATTERN.search(element.text)
        if generated_match:
            generated_at = datetime.strptime(
                f"{generated_match.group(1)} {generated_match.group(2)}:00",
                "%d/%m/%Y %H:%M:%S",
            )

    if not account_id:
        raise ValueError("Não foi possível identificar o número da conta no PDF PicPay 2025.")

    start_date, end_date = parse_period_lines(first_page)

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


def find_nearby_text(
    page_elements: list[PdfTextElement],
    *,
    x_min: float,
    x_max: float,
    y_center: float,
    y_tolerance: float = 10.0,
) -> str | None:
    candidates = [
        element
        for element in page_elements
        if x_min <= element.x <= x_max and abs(element.y - y_center) <= y_tolerance
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (abs(item.y - y_center), item.x))
    return candidates[0].text


def parse_transactions_from_page(page_elements: list[PdfTextElement]) -> list[StatementTransaction]:
    transactions: list[StatementTransaction] = []
    current_date: datetime | None = None

    for element in sorted(page_elements, key=lambda item: (-item.y, item.x)):
        if DATE_HEADER_PATTERN.match(element.text):
            current_date = parse_portuguese_date(element.text)
            continue

        if not TIME_PATTERN.match(element.text) or current_date is None:
            continue

        txn_type = find_nearby_text(page_elements, x_min=100, x_max=180, y_center=element.y)
        amount_text = find_nearby_text(page_elements, x_min=490, x_max=540, y_center=element.y)
        origin_text = find_nearby_text(page_elements, x_min=220, x_max=340, y_center=element.y)

        if not txn_type or not amount_text or not AMOUNT_PATTERN.match(amount_text):
            continue

        memo_parts = [txn_type]
        if origin_text:
            memo_parts.append(origin_text)

        transactions.append(
            StatementTransaction(
                posted_at=parse_datetime_br(current_date.strftime("%d/%m/%Y"), f"{element.text}:00"),
                memo=" - ".join(memo_parts),
                amount=parse_brl_amount(amount_text),
                balance=None,
            )
        )

    return transactions


def parse_pdf(input_path: str | Path) -> StatementData:
    pdf_bytes = Path(input_path).read_bytes()
    pages = extract_text_elements(pdf_bytes)
    metadata = extract_statement_metadata(pages)

    transactions: list[StatementTransaction] = []
    for page in pages:
        transactions.extend(parse_transactions_from_page(page))

    return StatementData(
        account_id=metadata.account_id,
        account_type=metadata.account_type,
        bank_id=metadata.bank_id,
        currency=metadata.currency,
        generated_at=metadata.generated_at,
        start_date=metadata.start_date,
        end_date=metadata.end_date,
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
