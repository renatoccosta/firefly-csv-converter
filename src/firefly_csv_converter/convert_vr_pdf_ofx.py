import re
import sys
import zlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from firefly_csv_converter._ofx_common import StatementData, StatementTransaction, build_ofx


DATETIME_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")
DATE_ONLY_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{2}$")


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
    text_array_match = re.search(rb"\[(.*?)\]\s*TJ", block, re.S)
    if text_array_match:
        parts = [
            unescape_pdf_string(match).decode("latin1", "replace")
            for match in re.findall(rb"\((.*?)\)", text_array_match.group(1), re.S)
        ]
        return "".join(parts).strip()

    text_match = re.search(rb"\((.*?)\)\s*Tj", block, re.S)
    if text_match:
        return unescape_pdf_string(text_match.group(1)).decode("latin1", "replace").strip()

    return ""


def extract_text_elements(pdf_bytes: bytes) -> list[list[tuple[float, float, str]]]:
    pages: list[list[tuple[float, float, str]]] = []

    for stream_match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        raw_stream = stream_match.group(1)
        try:
            stream = zlib.decompress(raw_stream)
        except zlib.error:
            continue

        page_elements: list[tuple[float, float, str]] = []
        for block_match in re.finditer(rb"BT\s*(.*?)\s*ET", stream, re.S):
            block = block_match.group(1)
            position_match = re.search(rb"1 0 0 1 ([\-0-9.]+) ([\-0-9.]+) Tm", block)
            if not position_match:
                continue

            text = decode_text_block(block)
            if text:
                page_elements.append(
                    (
                        float(position_match.group(2)),
                        float(position_match.group(1)),
                        text,
                    )
                )

        has_transaction_rows = any(
            DATETIME_PATTERN.match(text) or DATE_ONLY_PATTERN.match(text) for _, _, text in page_elements
        )
        has_vr_markers = any(
            text in {"DATA_HORA", "OPERACAO", "VALOR"} or "Consumo Confirmado" in text or "Disponibilização" in text
            for _, _, text in page_elements
        )
        if has_transaction_rows and has_vr_markers:
            pages.append(page_elements)

    return pages


def parse_amount(value_text: str, operation_text: str) -> Decimal:
    value = Decimal(value_text.replace(".", "").replace(",", "."))
    if "disponibiliza" in operation_text.lower():
        return value
    return -value


def parse_posted_at(value: str) -> datetime:
    if DATETIME_PATTERN.match(value):
        return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
    if DATE_ONLY_PATTERN.match(value):
        return datetime.strptime(value, "%d/%m/%y")
    raise ValueError(f"Data/Hora não reconhecida no PDF da VR: {value}")


def extract_metadata(first_page: list[tuple[float, float, str]]) -> tuple[str, str | None]:
    account_id = ""
    generated_at = None

    for _, _, text in first_page:
        if text.isdigit() and len(text) >= 12 and not account_id:
            account_id = text
        if re.match(r"^\d{2}/\d{2}/\d{4} às \d{2}:\d{2}:\d{2}$", text):
            generated_at = text

    if not account_id:
        raise ValueError("Não foi possível identificar o cartão/conta no PDF da VR.")

    return account_id, generated_at


def parse_transactions(pages: list[list[tuple[float, float, str]]]) -> list[StatementTransaction]:
    transactions: list[StatementTransaction] = []

    for page in pages:
        rows: dict[float, list[tuple[float, str]]] = {}
        for y, x, text in page:
            rows.setdefault(y, []).append((x, text))

        for y in sorted(rows.keys(), reverse=True):
            cells = sorted(rows[y], key=lambda item: item[0])
            if not cells:
                continue

            row = {x: text for x, text in cells}
            datetime_text = next(
                (
                    text
                    for x, text in cells
                    if x < 120 and (DATETIME_PATTERN.match(text) or DATE_ONLY_PATTERN.match(text))
                ),
                None,
            )
            if not datetime_text:
                continue

            operation_text = next((text for x, text in cells if 680 <= x <= 900), "")
            amount_text = next((text for x, text in cells if x >= 990 and re.search(r"\d,\d{2}$", text)), None)
            razao_social = next((text for x, text in cells if 280 <= x < 520), None)
            nome_estabelecimento = next((text for x, text in cells if 520 <= x < 680), None)

            if not operation_text or not amount_text:
                continue

            if razao_social and nome_estabelecimento:
                name = f"{razao_social} - {nome_estabelecimento}"
            else:
                name = nome_estabelecimento or razao_social or operation_text

            transactions.append(
                StatementTransaction(
                    posted_at=parse_posted_at(datetime_text),
                    memo=operation_text,
                    amount=parse_amount(amount_text, operation_text),
                    balance=None,
                    name=name,
                )
            )

    return transactions


def parse_pdf(input_path: str | Path) -> StatementData:
    pdf_bytes = Path(input_path).read_bytes()
    pages = extract_text_elements(pdf_bytes)
    if not pages:
        raise ValueError("Nenhuma página do extrato VR foi identificada no PDF.")

    account_id, generated_at_text = extract_metadata(pages[0])
    transactions = parse_transactions(pages)

    generated_at = None
    if generated_at_text:
        generated_at = None

    return StatementData(
        account_id=account_id,
        account_type="CHECKING",
        bank_id="VR",
        currency="BRL",
        generated_at=generated_at,
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
