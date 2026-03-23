from pathlib import Path

import pytest

from statement_converter import statement_converter
from statement_converter import convert_picpay_pdf_ofx as picpay_auto_converter
from statement_converter.converter_registry import ConverterRegistry


def test_main_without_args_shows_help(capsys: pytest.CaptureFixture[str]):
    exit_code = statement_converter.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "statement-converter" in captured.out
    assert "Conversores disponiveis" in captured.out


def test_model_completion_uses_registered_models(monkeypatch: pytest.MonkeyPatch):
    test_registry = ConverterRegistry()

    @test_registry.register(
        input_format="pdf",
        output_format="ofx",
        model="vr",
        description="Conversor fake para teste",
        aliases=("vale-refeicao",),
    )
    def fake_handler(args):
        del args

    monkeypatch.setattr(statement_converter, "registry", test_registry)

    completions = statement_converter._complete_model("v", None)

    assert "vr" in completions
    assert "vale-refeicao" in completions


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
        ["--model", "picpay", str(input_path), str(output_path)],
        converter_registry=test_registry,
    )

    assert exit_code == 0
    assert calls == [(input_path, output_path)]


def test_main_accepts_output_directory_for_single_file(tmp_path: Path):
    calls: list[tuple[Path, Path]] = []
    test_registry = ConverterRegistry()

    @test_registry.register(
        input_format="pdf",
        output_format="ofx",
        model="vr",
        description="Conversor fake para teste",
    )
    def fake_handler(args):
        calls.append((args.input_path, args.output_path))
        args.output_path.write_text("ok", encoding="utf-8")

    input_path = tmp_path / "extrato.pdf"
    output_dir = tmp_path / "saida"
    input_path.write_text("fake", encoding="utf-8")

    exit_code = statement_converter.main(
        ["--model", "vr", str(input_path), str(output_dir)],
        converter_registry=test_registry,
    )

    expected_output = output_dir / "extrato.ofx"
    assert exit_code == 0
    assert calls == [(input_path, expected_output)]
    assert expected_output.read_text(encoding="utf-8") == "ok"


def test_main_reports_unknown_converter(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        statement_converter.main(
            ["--model", "desconhecido", "entrada.pdf", "saida.csv"]
        )

    captured = capsys.readouterr()
    assert excinfo.value.code == 2
    assert "nenhum conversor foi encontrado para o modelo desconhecido" in captured.err


def test_main_requires_due_date_for_c6_csv(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        statement_converter.main(
            ["--model", "c6-credit-csv", "fatura.csv", "fatura.ofx"]
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
        ["--model", "picpay", str(input_path), str(output_path)]
    )
    picpay_auto_converter.process_pdf(args.input_path, args.output_path)

    assert calls == ["2025", "2024"]
    assert output_path.read_text(encoding="utf-8") == "ok"


def test_main_processes_directory_and_continues_after_failures(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    test_registry = ConverterRegistry()
    calls: list[tuple[str, str]] = []

    @test_registry.register(
        input_format="pdf",
        output_format="ofx",
        model="vr",
        description="Conversor fake para teste",
    )
    def fake_handler(args):
        calls.append((args.input_path.name, args.output_path.name))
        if args.input_path.stem == "broken":
            raise ValueError("arquivo corrompido")
        args.output_path.write_text(f"convertido:{args.input_path.name}", encoding="utf-8")

    input_dir = tmp_path / "entrada"
    output_dir = tmp_path / "saida"
    input_dir.mkdir()
    (input_dir / "ok.pdf").write_text("ok", encoding="utf-8")
    (input_dir / "broken.pdf").write_text("broken", encoding="utf-8")
    (input_dir / "ignorar.txt").write_text("ignorar", encoding="utf-8")

    exit_code = statement_converter.main(
        ["--model", "vr", str(input_dir), str(output_dir)],
        converter_registry=test_registry,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert calls == [("broken.pdf", "broken.ofx"), ("ok.pdf", "ok.ofx")]
    assert (output_dir / "ok.ofx").read_text(encoding="utf-8") == "convertido:ok.pdf"
    assert not (output_dir / "broken.ofx").exists()
    assert "arquivo corrompido" in captured.err
    assert "1 sucesso(s), 1 falha(s)" in captured.out
