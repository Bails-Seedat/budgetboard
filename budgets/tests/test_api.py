import io
from datetime import date
from decimal import Decimal

import pytest

from budgets.models import Budget, Category, Transaction


@pytest.mark.django_db
def test_unauthenticated_request_rejected(api_client):
    response = api_client.get("/api/transactions/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_register_and_obtain_token(api_client):
    response = api_client.post(
        "/api/auth/register/",
        {"username": "carol", "email": "carol@example.com", "password": "s3curepass!"},
    )
    assert response.status_code == 201

    token_response = api_client.post(
        "/api/auth/token/", {"username": "carol", "password": "s3curepass!"}
    )
    assert token_response.status_code == 200
    assert "access" in token_response.data


@pytest.mark.django_db
def test_user_cannot_see_other_users_transactions(auth_client, other_auth_client, user, other_user):
    Transaction.objects.create(user=user, date=date(2026, 10, 1), description="Mine", amount=Decimal("10"))
    Transaction.objects.create(
        user=other_user, date=date(2026, 10, 1), description="Theirs", amount=Decimal("20")
    )

    response = auth_client.get("/api/transactions/")
    descriptions = [t["description"] for t in response.data["results"]] if "results" in response.data else [
        t["description"] for t in response.data
    ]
    assert descriptions == ["Mine"]


@pytest.mark.django_db
def test_user_cannot_fetch_other_users_transaction_by_id(auth_client, other_user):
    other_txn = Transaction.objects.create(
        user=other_user, date=date(2026, 10, 1), description="Theirs", amount=Decimal("20")
    )
    response = auth_client.get(f"/api/transactions/{other_txn.id}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_csv_import_endpoint(auth_client):
    csv_content = "Date,Description,Amount\n2026-10-01,Coffee,45.00\n"
    file_obj = io.BytesIO(csv_content.encode("utf-8"))
    file_obj.name = "statement.csv"

    response = auth_client.post("/api/import/", {"file": file_obj}, format="multipart")

    assert response.status_code == 201
    assert response.data["created"] == 1
    assert Transaction.objects.count() == 1


@pytest.mark.django_db
def test_import_without_file_returns_400(auth_client):
    response = auth_client.post("/api/import/", {}, format="multipart")
    assert response.status_code == 400


@pytest.mark.django_db
def test_dashboard_endpoint_reflects_budget_and_spend(auth_client, user):
    groceries = Category.objects.create(user=user, name="Groceries")
    Budget.objects.create(user=user, category=groceries, month=date(2026, 10, 1), limit_amount=Decimal("300"))
    Transaction.objects.create(
        user=user, date=date(2026, 10, 10), description="Shop", amount=Decimal("350"), category=groceries
    )

    response = auth_client.get("/api/dashboard/?month=2026-10")

    assert response.status_code == 200
    assert response.data["month"] == "2026-10-01"
    row = response.data["categories"][0]
    assert row["over_budget"] is True
    assert Decimal(str(row["actual_spend"])) == Decimal("350")


@pytest.mark.django_db
def test_dashboard_invalid_month_format_returns_400(auth_client):
    response = auth_client.get("/api/dashboard/?month=not-a-month")
    assert response.status_code == 400


@pytest.mark.django_db
def test_end_to_end_import_then_dashboard(auth_client, user):
    groceries = Category.objects.create(user=user, name="Groceries")
    from budgets.models import CategoryRule

    CategoryRule.objects.create(user=user, keyword="woolworths", category=groceries)
    Budget.objects.create(user=user, category=groceries, month=date(2026, 10, 1), limit_amount=Decimal("100"))

    csv_content = "Date,Description,Amount\n2026-10-02,Woolworths,150.00\n"
    file_obj = io.BytesIO(csv_content.encode("utf-8"))
    file_obj.name = "statement.csv"
    import_response = auth_client.post("/api/import/", {"file": file_obj}, format="multipart")
    assert import_response.status_code == 201
    assert import_response.data["created"] == 1

    dashboard_response = auth_client.get("/api/dashboard/?month=2026-10")
    row = dashboard_response.data["categories"][0]
    assert row["category_name"] == "Groceries"
    assert row["over_budget"] is True
