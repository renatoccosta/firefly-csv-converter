import tempfile
import os
import csv
from firefly_csv_converter.convert_ourocard_ofx import process_csv

# Sample minimal OFX content for test
OFX_SAMPLE = """\
OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>DEBIT</TRNTYPE>
            <DTPOSTED>20250407120000[-3:GMT]</DTPOSTED>
            <TRNAMT>-120.50</TRNAMT>
            <FITID>202504071</FITID>
            <NAME>SUPERMERCADO XYZ</NAME>
            <MEMO>COMPRA CARTAO</MEMO>
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>CREDIT</TRNTYPE>
            <DTPOSTED>20250410120000[-3:GMT]</DTPOSTED>
            <TRNAMT>3500.00</TRNAMT>
            <FITID>202504102</FITID>
            <NAME>SALARIO</NAME>
            <MEMO>CREDITO MENSAL</MEMO>
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
"""


def test_process_csv_generates_file():
    """Test if process_csv correctly generates the CSV output from OFX input."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "test.ofx")
        output_path = os.path.join(tmpdir, "output.csv")

        # Write sample OFX input
        with open(input_path, "w", encoding="utf-8") as f:
            f.write(OFX_SAMPLE)

        # Execute conversion
        process_csv(input_path, output_path)

        # Assert file was created
        assert os.path.exists(output_path), "Output CSV file was not created"

        # Validate content
        with open(output_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile, delimiter=";")
            rows = list(reader)

        assert len(rows) == 2, "Expected 2 transactions in the CSV"
        assert rows[0]["Type"] == "debit"
        assert rows[1]["Type"] == "credit"
        assert rows[0]["Date"].startswith("2025-04-07")
        assert rows[1]["Date"].startswith("2025-04-10")
        assert rows[0]["Amount"] == "-120,50"
        assert rows[1]["Amount"] == "3500,00"
        assert rows[0]["Id"] == "202504071"
        assert rows[1]["Id"] == "202504102"
        assert rows[0]["Memo"] == "COMPRA CARTAO"
        assert rows[1]["Memo"] == "CREDITO MENSAL"


def test_process_csv_handles_empty_input():
    """Test if process_csv gracefully handles empty OFX input."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "empty.ofx")
        output_path = os.path.join(tmpdir, "output.csv")

        # Write an empty OFX file
        with open(input_path, "w", encoding="utf-8") as f:
            f.write("<OFX></OFX>")

        process_csv(input_path, output_path)

        # Even if empty, should still create a CSV header
        assert os.path.exists(output_path)
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
        assert "Type;Date;Amount;Id;Memo" in content
