import csv
import re
import sys
from pathlib import Path
from io import StringIO

def parse_csv(input_file):
    """Parse CSV and return list of dicts (records)."""
    with open(input_file, newline='', encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)

        # Define new fieldnames: insert "Type" right after "Valor"
        fieldnames = []
        for fn in reader.fieldnames:
            if fn.strip('"') == "Valor":
                fieldnames.append("Valor")
                fieldnames.append("Type")
            else:
                fieldnames.append(fn.strip('"'))

        records = []
        for row in reader:
            cleaned_row = {k.strip('"'): v for k, v in row.items() if k.strip('"')}
            original_value = cleaned_row["Valor"].strip()

            m = re.match(r'([\d.,]+)\s*([CD])', original_value)
            if m:
                value, symbol = m.groups()
                cleaned_row["Valor"] = value
                cleaned_row["Type"] = symbol
            else:
                cleaned_row["Type"] = ""

            records.append(cleaned_row)

    return fieldnames, records

def process_csv(input_file, output_file):
    """Parse and write output CSV."""
    fieldnames, records = parse_csv(input_file)

    with open(output_file, "w", newline='', encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(records)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        script_name = Path(sys.argv[0]).name
        print(f"Usage: {script_name} <input.csv> <output.csv>")
        sys.exit(1)
    else:
        input_file = Path(sys.argv[1])
        output_file = Path(sys.argv[2])
        process_csv(input_file, output_file)
