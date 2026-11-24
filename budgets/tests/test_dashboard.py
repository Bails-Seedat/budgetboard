from datetime import date
from decimal import Decimal

import pytest

from budgets.dashboard import budget_vs_actual, spend_by_category
from budgets.models import Budget, Category, Transaction


@pytest.mark.django_db
def test_spend_by_category_only_counts_current_month(user):
    groceries = Category.objects.create(user=user, name="Groceries")
    Transaction.objects.create(
        user=user, date=date(2026, 10, 5), description="A", amount=Decimal("100"), category=groceries
    )
    Transaction.objects.create(
        user=user, date=date(2026, 9, 30), description="B", amount=Decimal("50"), category=groceries
    )

    totals = spend_by_category(user, date(2026, 10, 1))
    assert totals[groceries.id] == Decimal("100")


@pytest.mark.django_db
def test_spend_by_category_excludes_negative_amounts(user):
    groceries = Category.objects.create(user=user, name="Groceries")
    Transaction.objects.create(
        user=user, date=date(2026, 10, 5), description="Purchase", amount=Decimal("100"), category=groceries
    )
    Transaction.objects.create(
        user=user, date=date(2026, 10, 6), description="Refund", amount=Decimal("-30"), category=groceries
    )

    totals = spend_by_category(user, date(2026, 10, 1))
    assert totals[groceries.id] == Decimal("100")


@pytest.mark.django_db
def test_budget_vs_actual_flags_over_budget(user):
    groceries = Category.objects.create(user=user, name="Groceries")
    Budget.objects.create(user=user, category=groceries, month=date(2026, 10, 1), limit_amount=Decimal("200"))
    Transaction.objects.create(
        user=user, date=date(2026, 10, 5), description="A", amount=Decimal("250"), category=groceries
    )

    rows = budget_vs_actual(user, date(2026, 10, 1))
    assert len(rows) == 1
    row = rows[0]
    assert row["actual_spend"] == Decimal("250")
    assert row["remaining"] == Decimal("-50")
    assert row["over_budget"] is True


@pytest.mark.django_db
def test_budget_vs_actual_under_budget_not_flagged(user):
    groceries = Category.objects.create(user=user, name="Groceries")
    Budget.objects.create(user=user, category=groceries, month=date(2026, 10, 1), limit_amount=Decimal("200"))
    Transaction.objects.create(
        user=user, date=date(2026, 10, 5), description="A", amount=Decimal("120"), category=groceries
    )

    rows = budget_vs_actual(user, date(2026, 10, 1))
    row = rows[0]
    assert row["remaining"] == Decimal("80")
    assert row["over_budget"] is False


@pytest.mark.django_db
def test_budget_with_no_spend_shows_full_remaining(user):
    groceries = Category.objects.create(user=user, name="Groceries")
    Budget.objects.create(user=user, category=groceries, month=date(2026, 10, 1), limit_amount=Decimal("200"))

    rows = budget_vs_actual(user, date(2026, 10, 1))
    row = rows[0]
    assert row["actual_spend"] == Decimal("0")
    assert row["remaining"] == Decimal("200")


@pytest.mark.django_db
def test_december_month_rollover_does_not_crash(user):
    groceries = Category.objects.create(user=user, name="Groceries")
    Transaction.objects.create(
        user=user, date=date(2026, 12, 15), description="A", amount=Decimal("10"), category=groceries
    )
    totals = spend_by_category(user, date(2026, 12, 1))
    assert totals[groceries.id] == Decimal("10")
