"""PRD-CORTEX-005 — Zepto credit-card checkout. All MCP calls mocked; no live orders.

Covers: cart_hash, M-5 dispatcher, preview/place semantics (confirmOrder flag +
check_payment_status for card), response parsers, checkout-token lifecycle in the DB,
the three routes (issue / preview / checkout incl. double-tap, expiry, error), and a
static M-5 guard (order-tool name appears once, never in app.py).
"""
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import db
import zepto_client


# ── cart_hash ────────────────────────────────────────────────────────────────

class TestCartHash(unittest.TestCase):
    def test_order_independent(self):
        a = zepto_client._cart_hash([{"pvid": "x", "qty": 1}, {"pvid": "y", "qty": 2}])
        b = zepto_client._cart_hash([{"pvid": "y", "qty": 2}, {"pvid": "x", "qty": 1}])
        self.assertEqual(a, b)

    def test_qty_change_differs(self):
        a = zepto_client._cart_hash([{"pvid": "x", "qty": 1}])
        b = zepto_client._cart_hash([{"pvid": "x", "qty": 2}])
        self.assertNotEqual(a, b)

    def test_quantity_key_alias(self):
        self.assertEqual(
            zepto_client._cart_hash([{"pvid": "x", "quantity": 1}]),
            zepto_client._cart_hash([{"pvid": "x", "qty": 1}]),
        )


# ── M-5 dispatcher ───────────────────────────────────────────────────────────

class TestDispatcher(unittest.TestCase):
    def test_card_maps_to_online_payment(self):
        self.assertEqual(zepto_client._dispatch_tool("CARD"), "create_online_payment_order")
        self.assertEqual(zepto_client._dispatch_tool("card"), "create_online_payment_order")

    def test_unwired_methods_raise(self):
        for m in ("COD", "WALLET", "UPI", "", None, "bogus"):
            with self.assertRaises(ValueError):
                zepto_client._dispatch_tool(m)


# ── preview / place semantics ────────────────────────────────────────────────

class TestPreviewPlace(unittest.TestCase):
    def test_preview_uses_confirm_false(self):
        calls = []

        def fake_tool(tok, sid, name, args):
            calls.append((name, args))
            return json.dumps({"subtotal": 220, "delivery_fee": 30, "total": 250, "eta_minutes": 12})

        with patch.object(zepto_client, "_setup_for_checkout", return_value="sid"), \
             patch.object(zepto_client, "_mcp_tool", side_effect=fake_tool):
            prev = zepto_client.preview_order("tok", "CARD", "addr")

        self.assertEqual(calls[0][0], "create_online_payment_order")
        self.assertIs(calls[0][1]["confirmOrder"], False)
        self.assertEqual(prev["total"], 250)
        self.assertEqual(prev["eta_minutes"], 12)

    def test_place_card_confirms_and_fetches_payment_url(self):
        seen = []

        def fake_tool(tok, sid, name, args):
            seen.append((name, args))
            if name == "create_online_payment_order":
                return json.dumps({"order_id": "ORD9", "total": 250})
            if name == "check_payment_status":
                return json.dumps({"payment_url": "https://pay.zepto/abc"})
            return ""

        with patch.object(zepto_client, "_setup_for_checkout", return_value="sid"), \
             patch.object(zepto_client, "_mcp_tool", side_effect=fake_tool):
            res = zepto_client.place_order("tok", "CARD", "addr")

        # order placed with confirmOrder=True, then payment status polled once
        self.assertEqual(seen[0][0], "create_online_payment_order")
        self.assertIs(seen[0][1]["confirmOrder"], True)
        self.assertEqual(seen[1][0], "check_payment_status")
        self.assertIs(seen[1][1]["poll"], False)
        self.assertEqual(res["type"], "redirect")
        self.assertEqual(res["order_id"], "ORD9")
        self.assertEqual(res["payment_url"], "https://pay.zepto/abc")


# ── response parsers (text + JSON) ───────────────────────────────────────────

class TestParsers(unittest.TestCase):
    def test_methods_from_text(self):
        keys = {m["key"] for m in zepto_client._parse_methods(
            "Available: Cash on Delivery, Credit/Debit Card, UPI")}
        self.assertEqual({"COD", "CARD", "UPI"} & keys, {"COD", "CARD", "UPI"})

    def test_methods_always_offer_card(self):
        self.assertIn("CARD", {m["key"] for m in zepto_client._parse_methods("unrecognised blob")})

    def test_preview_from_human_text(self):
        p = zepto_client._parse_preview("Subtotal ₹220 · Delivery ₹30 · Total: ₹250 · ~12 min")
        self.assertEqual(p["total"], 250.0)
        self.assertEqual(p["eta_minutes"], 12)

    def test_order_and_payment_url(self):
        self.assertEqual(zepto_client._parse_order('{"order_id":"X1","total":99}')["order_id"], "X1")
        self.assertEqual(
            zepto_client._parse_payment_url("pay here https://rzp.io/x done"),
            "https://rzp.io/x",
        )

    def test_get_payment_methods_only_offers_wired(self):
        """v1 card-first: even if Zepto offers COD/UPI, only CARD is surfaced."""
        with patch.object(zepto_client, "_setup_for_checkout", return_value="sid"), \
             patch.object(zepto_client, "_mcp_tool",
                          return_value="Cash on Delivery, Credit/Debit Card, UPI"):
            methods = zepto_client.get_payment_methods("tok", "addr")
        self.assertEqual({m["key"] for m in methods}, {"CARD"})


# ── checkout-token lifecycle (DB) ────────────────────────────────────────────

class TestCheckoutTokenDB(unittest.TestCase):
    def test_issue_then_ok(self):
        tok, exp = db.create_pending_checkout("h1", "CARD", "addr", [{"pvid": "p", "qty": 1}])
        status, row = db.checkout_token_status(tok)
        self.assertEqual(status, "ok")
        self.assertEqual(row["cart_hash"], "h1")
        self.assertTrue(exp)

    def test_single_use_lock(self):
        tok, _ = db.create_pending_checkout("h", "CARD", "a", [{"pvid": "p", "qty": 1}])
        self.assertTrue(db.mark_checkout_used(tok, "ORD"))
        self.assertFalse(db.mark_checkout_used(tok, "ORD2"))  # already used → no second order
        self.assertEqual(db.checkout_token_status(tok)[0], "used")

    def test_cart_changed(self):
        tok, _ = db.create_pending_checkout("hash-A", "CARD", "a", [{"pvid": "p", "qty": 1}])
        self.assertEqual(db.checkout_token_status(tok, cart_hash="hash-B")[0], "cart_changed")

    def test_expired(self):
        with db.get_conn() as c:
            c.execute(
                """INSERT INTO pending_checkout_ops (token, cart_hash, address_id, items_json, status, expires_at)
                   VALUES ('exp-db', 'h', NULL, '[]', 'initiated', datetime('now','-1 minute'))""")
        self.assertEqual(db.checkout_token_status("exp-db")[0], "expired")

    def test_not_found(self):
        status, row = db.checkout_token_status("nope")
        self.assertEqual(status, "not_found")
        self.assertIsNone(row)

    def test_log_checkout_op_appends(self):
        db.log_checkout_op("t", "h", "CARD", "a", "[]", 250.0, "ORDLOG", "success")
        with db.get_conn() as c:
            n = c.execute("SELECT COUNT(*) FROM checkout_ops WHERE zepto_order_id='ORDLOG'").fetchone()[0]
        self.assertEqual(n, 1)


# ── routes ───────────────────────────────────────────────────────────────────

class TestCheckoutRoutes(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app_module = app_module
        self.client = app_module.app.test_client()

    def _auth(self):
        """Patch token retrieval + decrypt so routes see a connected Zepto account."""
        return (
            patch.object(self.app_module.db, "get_zepto_token", return_value=b"enc"),
            patch.object(self.app_module, "decrypt_token", return_value="tok"),
        )

    def test_payment_methods_issues_token(self):
        a, b = self._auth()
        with a, b, patch("zepto_client.get_payment_methods",
                         return_value=[{"key": "CARD", "label": "Credit/Debit Card"}]):
            r = self.client.post("/api/zepto/payment-methods",
                                 json={"cart_items": [{"pvid": "p", "qty": 1}], "address_id": "a"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("checkout_token", data)
        self.assertTrue(db.get_pending_checkout(data["checkout_token"]))

    def test_payment_methods_empty_cart_400(self):
        a, b = self._auth()
        with a, b:
            r = self.client.post("/api/zepto/payment-methods", json={"cart_items": []})
        self.assertEqual(r.status_code, 400)

    def test_not_connected_401(self):
        with patch.object(self.app_module.db, "get_zepto_token", return_value=None):
            r = self.client.post("/api/zepto/checkout", json={"checkout_token": "x"})
        self.assertEqual(r.status_code, 401)

    def test_checkout_success_then_double_tap_blocked(self):
        tok, _ = db.create_pending_checkout("h", "CARD", "a", [{"pvid": "p", "qty": 1}])
        a, b = self._auth()
        with a, b, patch("zepto_client.place_order",
                         return_value={"type": "redirect", "order_id": "ORD9",
                                       "payment_url": "https://pay", "total": 250}):
            r = self.client.post("/api/zepto/checkout",
                                 json={"checkout_token": tok, "payment_method": "CARD"})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["type"], "redirect")
        self.assertEqual(d["order_id"], "ORD9")
        self.assertEqual(d["payment_url"], "https://pay")

        # success row logged
        with db.get_conn() as c:
            n = c.execute("SELECT COUNT(*) FROM checkout_ops WHERE zepto_order_id='ORD9' AND status='success'").fetchone()[0]
        self.assertEqual(n, 1)

        # second tap on the same token → 422 used (no second order)
        a2, b2 = self._auth()
        with a2, b2, patch("zepto_client.place_order") as place2:
            r2 = self.client.post("/api/zepto/checkout",
                                  json={"checkout_token": tok, "payment_method": "CARD"})
        self.assertEqual(r2.status_code, 422)
        place2.assert_not_called()

    def test_checkout_error_logs_and_502(self):
        tok, _ = db.create_pending_checkout("h", "CARD", "a", [{"pvid": "p", "qty": 1}])
        a, b = self._auth()
        with a, b, patch("zepto_client.place_order", side_effect=Exception("Zepto says no")):
            r = self.client.post("/api/zepto/checkout",
                                 json={"checkout_token": tok, "payment_method": "CARD"})
        self.assertEqual(r.status_code, 502)
        with db.get_conn() as c:
            n = c.execute("SELECT COUNT(*) FROM checkout_ops WHERE token=? AND status='error'", (tok,)).fetchone()[0]
        self.assertEqual(n, 1)

    def test_checkout_expired_422(self):
        with db.get_conn() as c:
            c.execute(
                """INSERT INTO pending_checkout_ops (token, cart_hash, address_id, items_json, status, expires_at)
                   VALUES ('exp-route', 'h', NULL, '[]', 'initiated', datetime('now','-1 minute'))""")
        a, b = self._auth()
        with a, b:
            r = self.client.post("/api/zepto/checkout",
                                 json={"checkout_token": "exp-route", "payment_method": "CARD"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error"], "expired")


# ── M-5 static guard ─────────────────────────────────────────────────────────

class TestM5Guard(unittest.TestCase):
    def test_order_tool_name_appears_once_in_client(self):
        import inspect
        src = inspect.getsource(zepto_client)
        # Only in _TOOL_FOR_METHOD — no stray call site.
        self.assertEqual(src.count("create_online_payment_order"), 1)

    def test_no_create_tool_in_app(self):
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, "app.py"), encoding="utf-8") as f:
            app_src = f.read()
        for tool in ("create_online_payment_order", "create_order",
                     "create_wallet_order", "create_upi_reserve_pay_order"):
            self.assertNotIn(tool, app_src)


class TestCheckoutTemplateRenders(unittest.TestCase):
    """The index template still renders and carries the checkout UI hooks."""

    def setUp(self):
        import app as app_module
        self.client = app_module.app.test_client()

    def test_index_has_checkout_ui(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        for needle in ("checkout-overlay", "reviewCheckout(", "confirmAndPay(",
                       "Review &amp; Checkout", "/api/zepto/checkout"):
            self.assertIn(needle, html)


if __name__ == "__main__":
    unittest.main()
