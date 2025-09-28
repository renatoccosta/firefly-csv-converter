# Firefly CSV Converter

Firefly CSV Converter is a Python utility designed to transform raw bank statements, credit card invoices, and other financial text files into clean CSV files ready for import into [Firefly III](https://www.firefly-iii.org/).

The project provides customizable conversion scripts that handle recurring text transformations such as:
- Regex-based text replacements
- Column cleaning and restructuring
- Splitting value and credit/debit markers
- Generating valid CSV output for Firefly III

## Project Structure

```

firefly-csv-converter/
├── scripts/        # Source conversion scripts
├── tests/          # Unit tests (pytest)
├── samples/        # Example input files
├── output/         # Generated CSV files (ignored by git)
├── requirements.txt
├── README.md
└── LICENSE

````

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/renatoccosta/firefly-csv-converter.git
   cd firefly-csv-converter
   ```

2. Create and activate a Python virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Linux/macOS
   venv\Scripts\activate      # On Windows
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

Example converting a Banco do Brasil statement:

```bash
python scripts/convert_bb_cp.py samples/bb-cp.csv output/bb-cp-converted.csv
```

This will:

* Read the original `bb-cp.csv`
* Clean and restructure the `Value` column
* Add a `Type` column for `C` (credit) or `D` (debit)
* Save the processed file in `output/`

## Running Tests

Unit tests are written with [pytest](https://docs.pytest.org/).
To execute all tests:

```bash
pytest
```

## License

This project is licensed under the GNU General Public License v3.0.
See the [LICENSE](LICENSE) file for details.

```
