# Firefly CSV Converter

Firefly CSV Converter is a Python utility designed to transform raw bank statements, credit card invoices, and other financial text files into clean CSV files ready for import into [Firefly III](https://www.firefly-iii.org/).

The project provides customizable conversion scripts that handle recurring text transformations such as:
- Regex-based text replacements
- Column cleaning and restructuring
- Splitting value and credit/debit markers
- Generating valid CSV output for Firefly III
- Extracting PicPay statement transactions from text-based PDFs and generating OFX
- Extracting VR statement transactions from text-based PDFs and generating OFX
- Converting C6 credit card CSV invoices into OFX credit card statements

## Project Structure

```
firefly-csv-converter/
├── src/              # Package modules (conversion logic)
├── tests/            # Unit tests (pytest)
├── samples/          # Example input files
├── output/           # Generated CSV files (ignored by git)
├── .github/          # CI/workflow configs
├── pyproject.toml    # Build / packaging configuration
├── README.md         # This file
└── COPYING           # License
````

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/renatoccosta/firefly-csv-converter.git
   cd firefly-csv-converter
   ```

2. This project uses [Poetry](https://python-poetry.org/) to manage dependencies, build, install. Poetry should be installed with [PipX](https://pipx.pypa.io/stable/). Install PipX and Poetry:

   ```bash
   sudo apt update
   sudo apt install pipx
   pipx install poetry
   ```

3. Build/Install (Poetry takes care of venvs):

   ```bash
   poetry build
   poetry install
   ```
## Usage

Example converting a Banco do Brasil statement:

```bash
./convert_bb_cp samples/bb-cp.csv output/bb-cp-converted.csv
```

This will:

* Read the original `bb-cp.csv`
* Clean and restructure the `Value` column
* Add a `Type` column for `C` (credit) or `D` (debit)
* Save the processed file in `output/`

Example converting a PicPay PDF statement in the 2022-2024 layout to OFX:

```bash
poetry run convert-picpay-pdf-ofx-2024 samples-local/picpay/2022-2024/2024.pdf output/picpay-2024.ofx
```

Example converting a PicPay PDF statement in the 2025 layout to OFX:

```bash
poetry run convert-picpay-pdf-ofx-2025 samples-local/picpay/2025-x/2025.pdf output/picpay-2025.ofx
```

Example converting a VR PDF statement to OFX:

```bash
poetry run convert-vr-pdf-ofx samples-local/vr/2024.pdf output/vr-2024.ofx
```

Example converting an iFood PDF statement to OFX:

```bash
poetry run convert-ifood-pdf-ofx samples-local/ifood/extrato.pdf output/ifood.ofx
```

## Running Tests

Unit tests are written with [pytest](https://docs.pytest.org/).
To execute all tests:

```bash
poetry run pytest -v
```

## License

This project is licensed under the GNU General Public License v3.0.
See the [COPYING](COPYING) file for details.
