import argparse

from statement_converter.convert_picpay_pdf_ofx_2024 import process_pdf as process_picpay_pdf_ofx_2024
from statement_converter.convert_picpay_pdf_ofx_2025 import process_pdf as process_picpay_pdf_ofx_2025


def process_pdf(input_path, output_path) -> None:
    errors: list[str] = []

    for processor, label in (
        (process_picpay_pdf_ofx_2025, "picpay-2025"),
        (process_picpay_pdf_ofx_2024, "picpay-2024"),
    ):
        try:
            processor(input_path, output_path)
            return
        except ValueError as exc:
            errors.append(f"{label}: {exc}")

    joined_errors = "; ".join(errors) if errors else "nenhum layout compatível foi reconhecido"
    raise ValueError(
        "Nao foi possivel identificar automaticamente o layout do PDF do PicPay. "
        f"Tentativas: {joined_errors}"
    )


def _run(args: argparse.Namespace) -> None:
    process_pdf(args.input_path, args.output_path)


def register_converters(registry) -> None:
    registry.register(
        input_format="pdf",
        output_format="ofx",
        model="picpay",
        description="PicPay PDF para OFX com autodeteccao de layout",
    )(_run)


def main() -> None:
    import sys
    from pathlib import Path

    if len(sys.argv) < 3:
        script_name = Path(sys.argv[0]).name
        print(f"Usage: {script_name} <input.pdf> <output.ofx>")
        sys.exit(1)

    process_pdf(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
