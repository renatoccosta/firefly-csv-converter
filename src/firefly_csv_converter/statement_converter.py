import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from firefly_csv_converter.converter_registry import ConverterRegistry, ConverterSpec, registry


def _available_combinations(converter_registry: ConverterRegistry) -> str:
    lines = []
    for spec in converter_registry.all():
        required = ""
        if spec.required_options:
            labels = ", ".join(f"--{option.replace('_', '-')}" for option in spec.required_options)
            required = f" | extras: {labels}"
        lines.append(
            f"  - {spec.input_format} -> {spec.output_format} | model={spec.model} | {spec.description}{required}"
        )
    return "\n".join(lines)


def _ensure_builtin_converters_loaded(converter_registry: ConverterRegistry) -> None:
    if converter_registry is registry:
        converter_registry.load_package_converters("firefly_csv_converter")


def build_argument_parser(converter_registry: ConverterRegistry = registry) -> argparse.ArgumentParser:
    _ensure_builtin_converters_loaded(converter_registry)
    parser = argparse.ArgumentParser(
        prog="statement-converter",
        description="Converte extratos e faturas usando um unico ponto de entrada.",
        epilog=(
            "Exemplo:\n"
            "  statement-converter --in pdf --out ofx --model picpay entrada.pdf saida.ofx\n\n"
            "Conversores disponiveis:\n"
            f"{_available_combinations(converter_registry)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_path", type=Path, nargs="?")
    parser.add_argument("output_path", type=Path, nargs="?")
    parser.add_argument("--in", dest="input_format", help="Formato de entrada, por exemplo: csv, pdf, txt, xlsx, ofx.")
    parser.add_argument("--out", dest="output_format", help="Formato de saida, por exemplo: csv ou ofx.")
    parser.add_argument("--model", help="Modelo/instituicao do conversor, por exemplo: picpay, pb, rico, c6-credit.")
    parser.add_argument(
        "--due-date",
        dest="due_date",
        help="Opcao especifica para C6 CSV -> OFX. Aceita YYYY-MM-DD ou DD/MM/YYYY.",
    )
    return parser


def validate_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    converter_registry: ConverterRegistry = registry,
) -> ConverterSpec:
    if not args.input_format or not args.output_format or not args.model or not args.input_path or not args.output_path:
        parser.error(
            "os parametros --in, --out, --model, input_path e output_path sao obrigatorios para executar uma conversao"
        )

    converter = converter_registry.find(args.input_format, args.output_format, args.model)
    if converter is None:
        parser.error(
            "nenhum conversor foi encontrado para a combinacao "
            f"--in {args.input_format} --out {args.output_format} --model {args.model}.\n\n"
            "Use --help para ver as combinacoes suportadas."
        )

    missing_options = [
        f"--{option.replace('_', '-')}" for option in converter.required_options if not getattr(args, option, None)
    ]
    if missing_options:
        parser.error(f"o conversor selecionado exige opcoes extras: {', '.join(missing_options)}")

    return converter


def main(argv: Sequence[str] | None = None, converter_registry: ConverterRegistry = registry) -> int:
    _ensure_builtin_converters_loaded(converter_registry)
    parser = build_argument_parser(converter_registry)
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)
    converter = validate_args(parser, args, converter_registry)
    converter.handler(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
