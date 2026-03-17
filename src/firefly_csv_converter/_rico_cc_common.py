from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd


EXPECTED_COLUMNS = ["Movimentação", "Liquidação", "Lançamento", "Valor", "Saldo"]


@dataclass(frozen=True)
class RicoStatementRow:
    movimentacao: date | None
    liquidacao: date | None
    lancamento: str
    valor: Decimal | None
    saldo: Decimal | None


@dataclass(frozen=True)
class RicoStatementData:
    account_id: str | None
    generated_at: datetime | None
    rows: list[RicoStatementRow]


def _find_header_position(df_raw: pd.DataFrame) -> tuple[int, int]:
    for row_index, row in df_raw.iterrows():
        for col_index, cell in enumerate(row):
            if str(cell).strip().lower().startswith("movimenta"):
                return row_index, col_index
    raise ValueError("Header row with 'Movimentação' not found in the spreadsheet.")


def _normalize_dataframe(input_path: str | Path) -> pd.DataFrame:
    df_raw = pd.read_excel(input_path, header=None)
    header_row_idx, header_col_idx = _find_header_position(df_raw)

    df = pd.read_excel(input_path, header=header_row_idx)
    df = df.iloc[:, header_col_idx:]

    normalized_cols = {}
    for col in df.columns:
        col_lower = str(col).strip().lower()
        for expected in EXPECTED_COLUMNS:
            if col_lower.startswith(expected.lower()):
                normalized_cols[col] = expected
                break

    df = df.rename(columns=normalized_cols)
    df = df[[column for column in EXPECTED_COLUMNS if column in df.columns]]

    empty_row_indices = df.index[df.isnull().all(axis=1)].tolist()
    if empty_row_indices:
        df = df.loc[: empty_row_indices[0] - 1]

    for column in ("Movimentação", "Liquidação"):
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce").dt.date

    for column in ("Lançamento",):
        if column in df.columns:
            df[column] = df[column].fillna("").astype(str).str.strip()

    for column in ("Valor", "Saldo"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


def _extract_account_id(df_raw: pd.DataFrame) -> str | None:
    for row in df_raw.itertuples(index=False):
        for cell in row:
            text = str(cell).strip()
            if text.startswith("Conta Rico:"):
                return text.split(":", maxsplit=1)[1].strip() or None
    return None


def _extract_generated_at(df_raw: pd.DataFrame) -> datetime | None:
    for row in df_raw.itertuples(index=False):
        for cell in row:
            text = str(cell).strip()
            if text.startswith("Data da consulta:"):
                raw_value = text.split(":", maxsplit=1)[1].strip()
                return datetime.strptime(raw_value, "%d/%m/%Y %H:%M")
    return None


def parse_statement(input_path: str | Path) -> RicoStatementData:
    df_raw = pd.read_excel(input_path, header=None)
    df = _normalize_dataframe(input_path)

    def normalize_date(value):
        return None if pd.isna(value) else value

    rows = [
        RicoStatementRow(
            movimentacao=normalize_date(row.get("Movimentação")),
            liquidacao=normalize_date(row.get("Liquidação")),
            lancamento=row.get("Lançamento", ""),
            valor=None if pd.isna(row.get("Valor")) else Decimal(str(row.get("Valor"))).quantize(Decimal("0.01")),
            saldo=None if pd.isna(row.get("Saldo")) else Decimal(str(row.get("Saldo"))).quantize(Decimal("0.01")),
        )
        for row in df.to_dict(orient="records")
        if row.get("Lançamento") or not pd.isna(row.get("Valor"))
    ]

    return RicoStatementData(
        account_id=_extract_account_id(df_raw),
        generated_at=_extract_generated_at(df_raw),
        rows=rows,
    )


def parse_input_dataframe(input_path: str | Path) -> pd.DataFrame:
    df = _normalize_dataframe(input_path).copy()

    for column in ("Valor", "Saldo"):
        if column in df.columns:
            df[column] = df[column].map(
                lambda value: f"{value:.2f}".replace(".", ",") if pd.notnull(value) else ""
            )

    return df
