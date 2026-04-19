from datetime import datetime
from decimal import Decimal
import re

from statement_converter._ofx_common import StatementData, StatementTransaction, build_ofx, build_credit_card_ofx


def _statement_transaction() -> StatementTransaction:
    return StatementTransaction(
        posted_at=datetime(2025, 1, 10, 0, 0),
        memo="COMPRA TESTE",
        amount=Decimal("-10.00"),
        balance=Decimal("90.00"),
        name="COMPRA TESTE",
    )


def test_build_ofx_generates_distinct_fitids_for_equivalent_transactions():
    transaction = _statement_transaction()
    statement = StatementData(
        account_id="123",
        account_type="CHECKING",
        bank_id="BANK",
        currency="BRL",
        generated_at=datetime(2025, 1, 10, 12, 0),
        start_date=None,
        end_date=None,
        transactions=[transaction, transaction],
    )

    content = build_ofx(statement)
    fitids = [value.strip() for value in re.findall(r"<FITID>([^<]+)", content)]

    assert len(fitids) == 2
    assert fitids[0] != fitids[1]
    assert fitids == [
        "20250110000000-D-1000-COMPRATESTE-000001",
        "20250110000000-D-1000-COMPRATESTE-000002",
    ]


def test_build_credit_card_ofx_generates_distinct_fitids_for_equivalent_transactions():
    transaction = _statement_transaction()
    statement = StatementData(
        account_id="123",
        account_type="CREDITCARD",
        bank_id="BANK",
        currency="BRL",
        generated_at=datetime(2025, 1, 10, 12, 0),
        start_date=None,
        end_date=None,
        transactions=[transaction, transaction],
    )

    content = build_credit_card_ofx(statement, balance_as_of=datetime(2025, 1, 10, 0, 0))
    fitids = [value.strip() for value in re.findall(r"<FITID>([^<]+)", content)]

    assert len(fitids) == 2
    assert fitids[0] != fitids[1]
