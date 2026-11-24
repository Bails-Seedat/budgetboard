import io
from decimal import Decimal

import pytest

from budgets.importer import import_csv
from budgets.models import Category, CategoryRule, Transaction


def _csv_file(content: str):
    return io.BytesIO(content.encode("utf-8"))


@pytest.mark.django_db
def test_import_basic_rows_creates_transactions(user):
    content = (
        "Date,Description,Amount\n"
        "2026-10-01,Woolworths,250.00\n"
        "2026-10-02,Netflix,199.00\n"
    )
    result = import_csv(user, _csv_file(content))

    assert result.created == 2
    assert result.skipped_duplicate == 0
    assert result.skipped_invalid == 0
    assert Transaction.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_reimporting_same_file_is_idempotent(user):
    content = "Date,Description,Amount\n2026-10-01,Woolworths,250.00\n"

    first = import_csv(user, _csv_file(content))
    second = import_csv(user, _csv_file(content))

    assert first.created == 1
    assert second.created == 0
    assert second.skipped_duplicate == 1
    assert Transaction.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_malformed_rows_are_skipped_not_fatal(user):
    content = (
        "Date,Description,Amount\n"
        "2026-10-01,Good Row,100.00\n"
        "not-a-date,Bad Date,50.00\n"
        "2026-10-03,Bad Amount,not-a-number\n"
        "2026-10-04,,75.00\n"
    )
    result = import_csv(user, _csv_file(content))

    assert result.created == 1
    assert result.skipped_invalid == 3
    assert len(result.errors) == 3


@pytest.mark.django_db
def test_handles_alternate_bank_headers(user):
    content = (
        "Transaction Date,Merchant,Debit\n"
        "2026-10-05,Uber,85.50\n"
    )
    result = import_csv(user, _csv_file(content))

    assert result.created == 1
    txn = Transaction.objects.get(user=user)
    assert txn.description == "Uber"
    assert txn.amount == Decimal("85.50")


@pytest.mark.django_db
def test_parenthesized_negative_amount_and_currency_symbols(user):
    content = (
        "Date,Description,Amount\n"
        "2026-10-06,Refund,($45.00)\n"
        "2026-10-07,Rent,\"1,500.00\"\n"
    )
    result = import_csv(user, _csv_file(content))

    assert result.created == 2
    refund = Transaction.objects.get(description="Refund")
    rent = Transaction.objects.get(description="Rent")
    assert refund.amount == Decimal("-45.00")
    assert rent.amount == Decimal("1500.00")


@pytest.mark.django_db
def test_missing_required_columns_reports_error_and_imports_nothing(user):
    content = "Foo,Bar\n1,2\n"
    result = import_csv(user, _csv_file(content))

    assert result.created == 0
    assert any("Could not find required column" in e for e in result.errors)


@pytest.mark.django_db
def test_auto_categorization_uses_longest_matching_keyword(user):
    groceries = Category.objects.create(user=user, name="Groceries")
    general_market = Category.objects.create(user=user, name="General")
    CategoryRule.objects.create(user=user, keyword="market", category=general_market)
    CategoryRule.objects.create(user=user, keyword="whole foods market", category=groceries)

    content = "Date,Description,Amount\n2026-10-08,Whole Foods Market #12,64.20\n"
    import_csv(user, _csv_file(content))

    txn = Transaction.objects.get(user=user)
    assert txn.category == groceries


@pytest.mark.django_db
def test_uncategorized_when_no_rule_matches(user):
    content = "Date,Description,Amount\n2026-10-09,Mystery Charge,10.00\n"
    import_csv(user, _csv_file(content))

    txn = Transaction.objects.get(user=user)
    assert txn.category is None


@pytest.mark.django_db
def test_import_is_scoped_per_user(user, other_user):
    Category.objects.create(user=user, name="Groceries")
    rule_owner_cat = Category.objects.create(user=other_user, name="OtherGroceries")
    CategoryRule.objects.create(user=other_user, keyword="shop", category=rule_owner_cat)

    content = "Date,Description,Amount\n2026-10-10,Corner Shop,20.00\n"
    import_csv(user, _csv_file(content))

    txn = Transaction.objects.get(user=user)
    assert txn.category is None