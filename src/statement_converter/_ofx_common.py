import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class StatementTransaction:
    posted_at: datetime
    memo: str
    amount: Decimal
    balance: Decimal | None
    name: str | None = None


@dataclass(frozen=True)
class StatementData:
    account_id: str
    account_type: str
    bank_id: str
    currency: str
    generated_at: datetime | None
    start_date: datetime | None
    end_date: datetime | None
    transactions: list[StatementTransaction]


def parse_brl_amount(raw_amount: str) -> Decimal:
    cleaned = raw_amount.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    cleaned = cleaned.replace("−", "-").replace("+", "")
    return Decimal(cleaned)


def parse_datetime_br(date_text: str, time_text: str | None = None) -> datetime:
    time_part = time_text or "00:00:00"
    return datetime.strptime(f"{date_text} {time_part}", "%d/%m/%Y %H:%M:%S")


def format_ofx_timestamp(value: datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S")


def transaction_type(amount: Decimal) -> str:
    return "DEBIT" if amount < 0 else "CREDIT"


def fit_id(transaction: StatementTransaction) -> str:
    cents = int((abs(transaction.amount) * 100).quantize(Decimal("1")))
    memo_slug = re.sub(r"[^A-Z0-9]+", "", transaction.memo.upper())[:12] or "TXN"
    sign = "D" if transaction.amount < 0 else "C"
    return f"{format_ofx_timestamp(transaction.posted_at)}-{sign}-{cents}-{memo_slug}"


def build_ofx(statement: StatementData) -> str:
    if statement.transactions:
        start = min(transaction.posted_at for transaction in statement.transactions)
        end = max(transaction.posted_at for transaction in statement.transactions)
        ledger_balance = next(
            (transaction.balance for transaction in reversed(statement.transactions) if transaction.balance is not None),
            Decimal("0.00"),
        )
    else:
        start = statement.start_date or datetime.now()
        end = statement.end_date or start
        ledger_balance = Decimal("0.00")

    transaction_blocks = []
    for transaction in statement.transactions:
        transaction_blocks.append(
            "\n".join(
                [
                    "<STMTTRN>",
                    f"<TRNTYPE>{transaction_type(transaction.amount)}",
                    f"<DTPOSTED>{format_ofx_timestamp(transaction.posted_at)}",
                    f"<TRNAMT>{transaction.amount:.2f}",
                    f"<FITID>{fit_id(transaction)}",
                    f"<NAME>{transaction.name or transaction.memo}",
                    f"<MEMO>{transaction.memo}",
                    "</STMTTRN>",
                ]
            )
        )

    generated_at = statement.generated_at or datetime.now()

    return "\n".join(
        [
            "OFXHEADER:100",
            "DATA:OFXSGML",
            "VERSION:102",
            "SECURITY:NONE",
            "ENCODING:USASCII",
            "CHARSET:1252",
            "COMPRESSION:NONE",
            "OLDFILEUID:NONE",
            "NEWFILEUID:NONE",
            "",
            "<OFX>",
            "<SIGNONMSGSRSV1>",
            "<SONRS>",
            "<STATUS>",
            "<CODE>0",
            "<SEVERITY>INFO",
            "</STATUS>",
            f"<DTSERVER>{format_ofx_timestamp(generated_at)}",
            "<LANGUAGE>POR",
            "</SONRS>",
            "</SIGNONMSGSRSV1>",
            "<BANKMSGSRSV1>",
            "<STMTTRNRS>",
            "<TRNUID>1",
            "<STATUS>",
            "<CODE>0",
            "<SEVERITY>INFO",
            "</STATUS>",
            "<STMTRS>",
            "<CURDEF>BRL",
            "<BANKACCTFROM>",
            f"<BANKID>{statement.bank_id}",
            "<BRANCHID>0001",
            f"<ACCTID>{statement.account_id}",
            f"<ACCTTYPE>{statement.account_type}",
            "</BANKACCTFROM>",
            "<BANKTRANLIST>",
            f"<DTSTART>{format_ofx_timestamp(start)}",
            f"<DTEND>{format_ofx_timestamp(end)}",
            *transaction_blocks,
            "</BANKTRANLIST>",
            "<LEDGERBAL>",
            f"<BALAMT>{ledger_balance:.2f}",
            f"<DTASOF>{format_ofx_timestamp(end)}",
            "</LEDGERBAL>",
            "</STMTRS>",
            "</STMTTRNRS>",
            "</BANKMSGSRSV1>",
            "</OFX>",
            "",
        ]
    )


def build_credit_card_ofx(statement: StatementData, balance_as_of: datetime) -> str:
    if statement.transactions:
        start = min(transaction.posted_at for transaction in statement.transactions)
        end = max(transaction.posted_at for transaction in statement.transactions)
        ledger_balance = sum((transaction.amount for transaction in statement.transactions), Decimal("0.00"))
    else:
        start = statement.start_date or datetime.now()
        end = statement.end_date or start
        ledger_balance = Decimal("0.00")

    transaction_blocks = []
    for transaction in statement.transactions:
        transaction_blocks.append(
            "\n".join(
                [
                    "<STMTTRN>",
                    f"<TRNTYPE>{transaction_type(transaction.amount)}",
                    f"<DTPOSTED>{format_ofx_timestamp(transaction.posted_at)}",
                    f"<TRNAMT>{transaction.amount:.2f}",
                    f"<FITID>{fit_id(transaction)}",
                    f"<NAME>{transaction.name or transaction.memo}",
                    f"<MEMO>{transaction.memo}",
                    "</STMTTRN>",
                ]
            )
        )

    generated_at = statement.generated_at or datetime.now()

    return "\n".join(
        [
            "OFXHEADER:100",
            "DATA:OFXSGML",
            "VERSION:102",
            "SECURITY:NONE",
            "ENCODING:USASCII",
            "CHARSET:1252",
            "COMPRESSION:NONE",
            "OLDFILEUID:NONE",
            "NEWFILEUID:NONE",
            "",
            "<OFX>",
            "<SIGNONMSGSRSV1>",
            "<SONRS>",
            "<STATUS>",
            "<CODE>0",
            "<SEVERITY>INFO",
            "</STATUS>",
            f"<DTSERVER>{format_ofx_timestamp(generated_at)}",
            "<LANGUAGE>POR",
            "</SONRS>",
            "</SIGNONMSGSRSV1>",
            "<CREDITCARDMSGSRSV1>",
            "<CCSTMTTRNRS>",
            "<TRNUID>1",
            "<STATUS>",
            "<CODE>0",
            "<SEVERITY>INFO",
            "</STATUS>",
            "<CCSTMTRS>",
            "<CURDEF>BRL",
            "<CCACCTFROM>",
            f"<ACCTID>{statement.account_id}",
            "</CCACCTFROM>",
            "<BANKTRANLIST>",
            f"<DTSTART>{format_ofx_timestamp(start)}",
            f"<DTEND>{format_ofx_timestamp(end)}",
            *transaction_blocks,
            "</BANKTRANLIST>",
            "<LEDGERBAL>",
            f"<BALAMT>{ledger_balance:.2f}",
            f"<DTASOF>{format_ofx_timestamp(balance_as_of)}",
            "</LEDGERBAL>",
            "</CCSTMTRS>",
            "</CCSTMTTRNRS>",
            "</CREDITCARDMSGSRSV1>",
            "</OFX>",
            "",
        ]
    )
