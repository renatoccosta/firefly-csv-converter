# Firefly CSV Converter

Firefly CSV Converter is a Python utility designed to transform raw bank statements, credit card invoices, and other financial text files into clean CSV files ready for import into [Firefly III](https://www.firefly-iii.org/).

The project provides customizable conversion scripts that handle recurring text transformations such as:
- Regex-based text replacements
- Column cleaning and restructuring
- Splitting value and credit/debit markers
- Generating valid CSV output for Firefly III
- Extracting PicPay statement transactions from text-based PDFs and generating OFX
- Extracting VR statement transactions from text-based PDFs and generating OFX
- Extracting PB payroll statement transactions from PDFs and generating OFX
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

### Development install with Poetry

1. Clone the repository:
   ```bash
   git clone https://github.com/renatoccosta/firefly-csv-converter.git
   cd firefly-csv-converter
   ```

2. Install [Poetry](https://python-poetry.org/) with [PipX](https://pipx.pypa.io/stable/):

   ```bash
   sudo apt update
   sudo apt install pipx
   pipx install poetry
   ```

3. Install the project and its dependencies:

   ```bash
   poetry install
   ```

4. Run commands either through Poetry:

   ```bash
   poetry run statement-converter --help
   ```

   or by activating the virtual environment first:

   ```bash
   source "$(poetry env info --path)/bin/activate"
   statement-converter --help
   ```

### Install from distribution artifacts

After building the project with `poetry build`, the `dist/` directory will contain a wheel (`.whl`) and a source distribution (`.tar.gz`).

Install either artifact with `pip` in a Python environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install dist/firefly_csv_converter-0.1.2-py3-none-any.whl
```

or:

```bash
pip install dist/firefly_csv_converter-0.1.2.tar.gz
```

The console scripts declared in `pyproject.toml` are created automatically during installation. They can be called directly after the environment is activated, for example:

```bash
statement-converter --help
convert-bb-cp --help
```

If you install with `pip --user`, make sure your user scripts directory, usually `~/.local/bin`, is in your `PATH`.

## Usage

Unified CLI entry point:

```bash
statement-converter --model picpay samples-local/picpay/2025-x/2025.pdf output/picpay.ofx
```

The unified command accepts:
- `--model`: institution/model identifier
- `input_path`: source file
- `output_path`: destination file

The input and output formats are inferred from the selected model.

Some converters may require extra options. Example for C6 credit card CSV:

```bash
statement-converter --model c6-credit-csv --due-date 2021-04-05 samples-local/c6/credit/Fatura_2021-04-05.csv output/c6-credit.ofx
```

Example processing a full directory:

```bash
statement-converter --model vr samples/vr output
```

Run `statement-converter --help` to see the supported models.

### Shell completion

`statement-converter` supports TAB completion via `argcomplete`, including dynamic completion for `--model`.

After installing/updating the project with Poetry, enable it in Bash with:

```bash
eval "$(register-python-argcomplete statement-converter)"
```

To make it persistent, add that line to your shell startup file such as `~/.bashrc`.

Example converting a Banco do Brasil statement:

```bash
convert-bb-cp samples/bb-cp.csv output/bb-cp-converted.csv
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
poetry run pytest -v
```

## License

This project is licensed under the GNU General Public License v3.0.
See the [COPYING](COPYING) file for details.
