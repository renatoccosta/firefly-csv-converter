from pathlib import Path

import pytest

from firefly_csv_converter import statement_converter
from firefly_csv_converter import convert_picpay_pdf_ofx as picpay_auto_converter
from firefly_csv_converter.converter_registry import ConverterRegistry


def test_main_without_args_shows_help(capsys: pytest.CaptureFixture[str]):
    exit_code = statement_converter.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "statement-converter" in captured.out
    assert "Conversores disponiveis" in captured.out


def test_main_routes_to_matching_converter(tmp_path: Path):
    calls: list[tuple[Path, Path]] = []
    test_registry = ConverterRegistry()

    @test_registry.register(
        input_format="pdf",
        output_format="ofx",
        model="picpay",
        description="Conversor fake para teste",
    )
    def fake_handler(args):
        calls.append((args.input_path, args.output_path))

    input_path = tmp_path / "entrada.pdf"
    output_path = tmp_path / "saida.ofx"
    input_path.write_text("fake", encoding="utf-8")

    exit_code = statement_converter.main(
        ["--in", "pdf", "--out", "ofx", "--model", "picpay", str(input_path), str(output_path)],
        converter_registry=test_registry,
    )

    assert exit_code == 0
    assert calls == [(input_path, output_path)]


def test_main_reports_unknown_converter(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        statement_converter.main(
            ["--in", "pdf", "--out", "csv", "--model", "picpay", "entrada.pdf", "saida.csv"]
        )

    captured = capsys.readouterr()
    assert excinfo.value.code == 2
    assert "nenhum conversor foi encontrado" in captured.err


def test_main_requires_due_date_for_c6_csv(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        statement_converter.main(
            ["--in", "csv", "--out", "ofx", "--model", "c6", "fatura.csv", "fatura.ofx"]
        )

    captured = capsys.readouterr()
    assert excinfo.value.code == 2
    assert "--due-date" in captured.err


def test_process_picpay_auto_falls_back_to_2024(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls: list[str] = []

    def fail_2025(input_path: Path, output_path: Path) -> None:
        calls.append("2025")
        raise ValueError("layout 2025 invalido")

    def succeed_2024(input_path: Path, output_path: Path) -> None:
        calls.append("2024")
        output_path.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(picpay_auto_converter, "process_picpay_pdf_ofx_2025", fail_2025)
    monkeypatch.setattr(picpay_auto_converter, "process_picpay_pdf_ofx_2024", succeed_2024)

    input_path = tmp_path / "picpay.pdf"
    output_path = tmp_path / "picpay.ofx"
    input_path.write_text("fake pdf", encoding="utf-8")

    args = statement_converter.build_argument_parser().parse_args(
        ["--in", "pdf", "--out", "ofx", "--model", "picpay", str(input_path), str(output_path)]
    )
    picpay_auto_converter.process_pdf(args.input_path, args.output_path)

    assert calls == ["2025", "2024"]
    assert output_path.read_text(encoding="utf-8") == "ok"
