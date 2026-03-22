# PYTHON_ARGCOMPLETE_OK

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from firefly_csv_converter.converter_registry import ConverterRegistry, ConverterSpec, registry

try:
    import argcomplete
except ImportError:  # pragma: no cover - fallback for environments without the optional dependency installed yet
    argcomplete = None


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


def _complete_model(prefix: str, parsed_args, **kwargs) -> list[str]:
    del parsed_args, kwargs
    if not registry.all():
        _ensure_builtin_converters_loaded(registry)
    candidates: list[str] = []
    for spec in registry.all():
        candidates.extend([spec.model, *spec.aliases])
    return sorted(candidate for candidate in set(candidates) if candidate.startswith(prefix))


def _ensure_builtin_converters_loaded(converter_registry: ConverterRegistry) -> None:
    if converter_registry is registry:
        converter_registry.load_package_converters("firefly_csv_converter")


def _format_suffix(format_name: str) -> str:
    return f".{format_name.casefold().replace('_', '-')}"


def _is_directory_target(path: Path) -> bool:
    return path.exists() and path.is_dir() or not path.exists() and not path.suffix


def _collect_input_files(input_dir: Path, input_format: str) -> list[Path]:
    suffix = _format_suffix(input_format)
    return sorted(
        path for path in input_dir.iterdir() if path.is_file() and path.suffix.casefold() == suffix
    )


def _resolve_output_file(input_file: Path, output_target: Path, output_format: str, batch_mode: bool) -> Path:
    suffix = _format_suffix(output_format)

    if batch_mode or _is_directory_target(output_target):
        output_target.mkdir(parents=True, exist_ok=True)
        return output_target / f"{input_file.stem}{suffix}"

    return output_target


def _build_run_args(args: argparse.Namespace, input_path: Path, output_path: Path) -> argparse.Namespace:
    values = vars(args).copy()
    values["input_path"] = input_path
    values["output_path"] = output_path
    return argparse.Namespace(**values)


def _run_single_conversion(converter: ConverterSpec, args: argparse.Namespace, input_file: Path, output_file: Path) -> None:
    converter.handler(_build_run_args(args, input_file, output_file))


def execute_conversion(converter: ConverterSpec, args: argparse.Namespace) -> int:
    if args.input_path.is_dir():
        input_files = _collect_input_files(args.input_path, converter.input_format)
        if not input_files:
            print(
                f"Nenhum arquivo {_format_suffix(converter.input_format)} foi encontrado em {args.input_path}.",
                file=sys.stderr,
            )
            return 1

        success_count = 0
        failure_count = 0
        for input_file in input_files:
            output_file = _resolve_output_file(input_file, args.output_path, converter.output_format, batch_mode=True)
            try:
                _run_single_conversion(converter, args, input_file, output_file)
                success_count += 1
            except Exception as exc:
                print(f"Erro ao converter {input_file}: {exc}", file=sys.stderr)
                failure_count += 1

        print(f"Conversao em lote concluida: {success_count} sucesso(s), {failure_count} falha(s).")
        return 0 if failure_count == 0 else 1

    output_file = _resolve_output_file(args.input_path, args.output_path, converter.output_format, batch_mode=False)
    try:
        _run_single_conversion(converter, args, args.input_path, output_file)
    except Exception as exc:
        print(f"Erro ao converter {args.input_path}: {exc}", file=sys.stderr)
        return 1

    return 0


def build_argument_parser(converter_registry: ConverterRegistry = registry) -> argparse.ArgumentParser:
    _ensure_builtin_converters_loaded(converter_registry)
    parser = argparse.ArgumentParser(
        prog="statement-converter",
        description="Converte extratos e faturas usando um unico ponto de entrada.",
        epilog=(
            "Exemplo:\n"
            "  statement-converter --model picpay entrada.pdf saida.ofx\n\n"
            "Conversores disponiveis:\n"
            f"{_available_combinations(converter_registry)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_path", type=Path, nargs="?")
    parser.add_argument("output_path", type=Path, nargs="?")
    model_argument = parser.add_argument(
        "--model",
        help="Modelo/instituicao do conversor, por exemplo: picpay, pb, rico-ofx, c6-credit-csv.",
    )
    model_argument.completer = _complete_model
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
    if not args.model or not args.input_path or not args.output_path:
        parser.error(
            "os parametros --model, input_path e output_path sao obrigatorios para executar uma conversao"
        )

    converter = converter_registry.find_by_model(args.model)
    if converter is None:
        parser.error(
            f"nenhum conversor foi encontrado para o modelo {args.model}.\n\n"
            "Use --help para ver os modelos suportados."
        )

    if not args.input_path.exists():
        parser.error(f"o caminho de entrada nao existe: {args.input_path}")

    missing_options = [
        f"--{option.replace('_', '-')}" for option in converter.required_options if not getattr(args, option, None)
    ]
    if missing_options:
        parser.error(f"o conversor selecionado exige opcoes extras: {', '.join(missing_options)}")

    if args.input_path.is_dir():
        if args.output_path.exists() and not args.output_path.is_dir():
            parser.error("quando input_path for um diretorio, output_path tambem deve ser um diretorio")
        if not args.output_path.exists() and args.output_path.suffix:
            parser.error("quando input_path for um diretorio, output_path deve apontar para uma pasta")

    return converter


def main(argv: Sequence[str] | None = None, converter_registry: ConverterRegistry = registry) -> int:
    _ensure_builtin_converters_loaded(converter_registry)
    parser = build_argument_parser(converter_registry)
    if argcomplete is not None:
        argcomplete.autocomplete(parser)
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)
    converter = validate_args(parser, args, converter_registry)
    return execute_conversion(converter, args)


if __name__ == "__main__":
    raise SystemExit(main())
