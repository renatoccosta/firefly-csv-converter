import re
import csv
import sys
from pathlib import Path

# Regex for the main data table (supports negative numbers)
table_row_pattern = re.compile(
    r"^ *(?P<date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<capital_value>-?[\d.,]+)\s+"
    r"(?P<ir>-?[\d.,]+)\s+"
    r"(?P<iof>-?[\d.,]+)\s+"
    r"(?P<earnings>-?[\d.,]+)\s+"
    r"(?P<movement_value>-?[\d.,]+)\s+"
    r"(?P<current_value>-?[\d.,]+)\s*$",
    re.UNICODE
)

# Regex for the monthly summary lines
summary_pattern = re.compile(
    r"^\s*(?P<item>[A-ZÇÃÕÁÉÍÓÚÂÊÔÜ\s]+)\s+(?P<value>-?[\d.,]+)\s*$",
    re.UNICODE
)

def normalize_number(raw_value: str) -> str:
    """Remove all separators and insert a comma before the last two digits."""
    if not raw_value:
        return "0,00"
    value = raw_value.strip().replace(".", "").replace(",", "")
    negative = value.startswith("-")
    if negative:
        value = value[1:]
    value = value.zfill(3)
    formatted = f"{value[:-2]},{value[-2:]}"
    return f"-{formatted}" if negative else formatted

def parse_input(input_path: str | Path) -> tuple[list[str], list[list[str]]]:
    """
    Extracts the relevant data from the BB statement text file and writes it to CSV.
    """
    rows = []
    saldo_atual_date = None
    summary_items = {}

    with open(input_path, "r", encoding="utf-8") as infile:
        for raw_line in infile:
            line = raw_line.rstrip("\n")

            # Parse table section
            table_match = table_row_pattern.match(line)
            if table_match:
                data = table_match.groupdict()
                desc = " ".join(data["description"].split())

                # Ignore 'Saldo Anterior' and 'Saldo Atual'
                if desc.lower().startswith("saldo anterior") or desc.lower().startswith("saldo atual"):
                    if desc.lower().startswith("saldo atual"):
                        saldo_atual_date = data["date"]
                    continue

                rows.append([
                    data["date"],
                    desc,
                    normalize_number(data["movement_value"])
                ])
                continue

            # Parse summary section
            summary_match = summary_pattern.match(line)
            if summary_match:
                item = " ".join(summary_match["item"].split())
                value = summary_match["value"]
                summary_items[item.upper()] = value

    # Add summary items of interest (non-zero)
    if saldo_atual_date:
        for label in ["RENDIMENTO BRUTO", "IMPOSTO DE RENDA", "IOF"]:
            if label in summary_items:
                val = summary_items[label]
                numeric = val.replace(".", "").replace(",", "")
                if numeric != "0" * len(numeric):  # not zero
                    rows.append([
                        saldo_atual_date,
                        label.title(),
                        normalize_number(val)
                    ])
    
    fieldnames = ["Data", "Histórico", "Valor Movimento"]

    return fieldnames, rows

def process_csv(input_file, output_file):
    """Parse and write output CSV."""
    fieldnames, rows = parse_input(input_file)

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";", quoting=csv.QUOTE_ALL)
        writer.writerow(fieldnames)
        writer.writerows(rows)

    print(f"CSV successfully generated: {output_file} ({len(rows)} rows)")


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