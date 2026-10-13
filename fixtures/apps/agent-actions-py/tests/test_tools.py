from app.tools import search_orders


def test_search_orders_filters_by_email():
    assert [o["order_id"] for o in search_orders("ada@example.com")] == ["KW-1001", "KW-1002"]


def test_unknown_customer_has_no_orders():
    assert search_orders("nobody@example.com") == []
