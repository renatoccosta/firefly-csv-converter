import pandas as pd
import io
import sys
from pathlib import Path

def parse_input(input_path: str | Path) -> pd.DataFrame:
    # Expected table columns (in Portuguese as in the spreadsheet)
    expected_columns = ["Movimentação", "Liquidação", "Lançamento", "Valor", "Saldo"]

    # Read the Excel file without assuming headers
    df_raw = pd.read_excel(input_path, header=None)

    # Detect the header row and starting column dynamically
    header_row_idx = None
    header_col_idx = None

    for i, row in df_raw.iterrows():
        for j, cell in enumerate(row):
            if str(cell).strip().lower().startswith("movimenta"):
                header_row_idx = i
                header_col_idx = j
                break
        if header_row_idx is not None:
            break

    if header_row_idx is None:
        raise ValueError("Header row with 'Movimentação' not found in the spreadsheet.")

    # Read again with the detected header
    df = pd.read_excel(input_path, header=header_row_idx)

    # Keep only columns starting from the detected header column
    df = df.iloc[:, header_col_idx:]

    # Normalize column names for flexible matching
    normalized_cols = {}
    for col in df.columns:
        col_lower = str(col).strip().lower()
        for expected in expected_columns:
            if col_lower.startswith(expected.lower()):
                normalized_cols[col] = expected
                break

    # Rename columns using the normalized mapping
    df = df.rename(columns=normalized_cols)

    # Keep only expected columns that were found
    df = df[[c for c in expected_columns if c in df.columns]]

    # Drop empty rows
    #df = df.dropna(how="all")

    # Find the first completely empty row after data starts
    empty_row_indices = df.index[df.isnull().all(axis=1)].tolist()
    if empty_row_indices:
        # Truncate data up to the first empty row (exclusive)
        df = df.loc[:empty_row_indices[0] - 1]

    # Remove time components from date columns
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ["moviment", "liquida"]):
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    # Format numeric columns (comma as decimal separator, no thousand separator)
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ["valor", "saldo"]):
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].map(lambda x: f"{x:.2f}".replace(".", ",") if pd.notnull(x) else "")

    return df

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

if __name__ == "__main__":
    main()