import sys
from pathlib import Path

from firefly_csv_converter._rico_cc_common import parse_input_dataframe


def parse_input(input_path: str | Path):
    return parse_input_dataframe(input_path)

def process_csv(input_file, output_file):
    """Parse and write output CSV."""

    df = parse_input(input_file)
    # Save the cleaned data to CSV with semicolon separator
    df.to_csv(output_file, index=False, sep=";", encoding="utf-8-sig")
    print(f"Conversion completed successfully. Output file: {output_file}")

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


def _run(args):
    process_csv(args.input_path, args.output_path)


def register_converters(registry):
    registry.register(
        input_format="xlsx",
        output_format="csv",
        model="rico-csv",
        description="Rico XLSX para CSV",
        aliases=("rico-xlsx-csv",),
    )(_run)

if __name__ == "__main__":
    main()
