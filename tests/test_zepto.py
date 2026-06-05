"""
Test suite for PRD-CORTEX-003: Zepto Cart from Grocery List.
Covers 36 TCs: Unit, Integration, Security, Code Inspection.
No real Zepto API calls. All MCP calls are mocked.
"""
import sys, os, json, time, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Mock anthropic and cryptography modules before importing app modules
_mock_anthropic = MagicMock()
with patch.dict('sys.modules', {'anthropic': _mock_anthropic}):
    pass

# ── Fixtures / Helpers ──────────────────────────────────────────────────────

def _make_mcp_response(products):
    """Return a mock requests.Response for a Zepto MCP search call."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "jsonrpc": "2.0",
        "id": "test-id",
        "result": {"products": products},
    }
    return mock_resp


def _make_cart_response(success=True):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "jsonrpc": "2.0",
        "id": "test-id",
        "result": {"cart_id": "abc123", "added": success},
    }
    return mock_resp


SAMPLE_PRODUCTS = [
    {"id": "prod-001", "name": "Amul Milk 1L", "price": 68, "unit": "1 L"},
    {"id": "prod-002", "name": "Amul Milk 500ml", "price": 36, "unit": "500 ml"},
]


# ── Unit: zepto_client.py ───────────────────────────────────────────────────

class TestFernetEncryption(unittest.TestCase):
    """TC-01–TC-04: Fernet encrypt/decrypt."""

    def setUp(self):
        from cryptography.fernet import Fernet
        self.key = Fernet.generate_key().decode()

    def test_encrypt_produces_bytes(self):
        import zepto_client
        with patch.object(zepto_client, 'FERNET_KEY', self.key):
            ct = zepto_client.encrypt_token("my_access_token")
            self.assertIsInstance(ct, bytes)

    def test_decrypt_roundtrip(self):
        import zepto_client
        with patch.object(zepto_client, 'FERNET_KEY', self.key):
            original = "real_zepto_access_token_abc123"
            ct = zepto_client.encrypt_token(original)
            self.assertEqual(zepto_client.decrypt_token(ct), original)

    def test_decrypt_tampered_raises(self):
        import zepto_client
        with patch.object(zepto_client, 'FERNET_KEY', self.key):
            with self.assertRaises(ValueError):
                zepto_client.decrypt_token(b"this-is-not-valid-ciphertext")

    def test_no_fernet_key_raises(self):
        import zepto_client
        with patch.object(zepto_client, 'FERNET_KEY', ''):
            with self.assertRaises(ValueError):
                zepto_client.encrypt_token("test")


class TestMcpCall(unittest.TestCase):
    """TC-05–TC-07: _mcp_tool sends correct JSON-RPC payload and parses SSE."""

    @patch('requests.post')
    def test_sends_bearer_header(self, mock_post):
        payload = json.dumps({"jsonrpc": "2.0", "id": "t", "result": {"content": [{"type": "text", "text": "ok"}]}})
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = f"data: {payload}\n".encode("utf-8")
        mock_post.return_value = mock_resp
        import zepto_client
        zepto_client._mcp_tool("tok123", "sess123", "search_products", {"query": "milk"})
        call_kwargs = mock_post.call_args
        self.assertIn('Authorization', str(call_kwargs))

    def test_parse_product_list_returns_structured_list(self):
        text = (
            "1. Amul Milk 1L | Full Cream - ₹68 (1 L)\n"
            "2. Amul Milk 500ml - ₹36 (500 ml)\n"
            "---\n"
            "[1] pvid: 11111111-1111-1111-1111-111111111111, spid: 22222222-2222-2222-2222-222222222222\n"
            "[2] pvid: 33333333-3333-3333-3333-333333333333, spid: 44444444-4444-4444-4444-444444444444\n"
        )
        import zepto_client
        result = zepto_client._parse_product_list(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["pvid"], "11111111-1111-1111-1111-111111111111")

    @patch('requests.post')
    def test_mcp_error_raises_value_error(self, mock_post):
        payload = json.dumps({"jsonrpc": "2.0", "id": "x", "error": {"code": -32601, "message": "Tool not found"}})
        err_resp = MagicMock()
        err_resp.raise_for_status = MagicMock()
        err_resp.content = f"data: {payload}\n".encode("utf-8")
        mock_post.return_value = err_resp
        import zepto_client
        with self.assertRaises(ValueError):
            zepto_client._mcp_tool("tok", "sess123", "bad_tool", {})


class TestSearchAllItems(unittest.TestCase):
    """TC-08–TC-11: parallel search with ThreadPoolExecutor."""

    PRODUCT_TEXT = (
        "1. Amul Milk 1L - ₹68 (1 L)\n"
        "---\n"
        "[1] pvid: 11111111-1111-1111-1111-111111111111, spid: 22222222-2222-2222-2222-222222222222\n"
    )

    def test_returns_dict_keyed_by_item(self):
        import zepto_client
        with patch.object(zepto_client, '_setup_context', return_value=("sess123", set())):
            with patch.object(zepto_client, '_mcp_tool', return_value=self.PRODUCT_TEXT):
                result = zepto_client.search_all_items("tok", ["milk", "eggs"])
        self.assertIn("milk", result)
        self.assertIn("eggs", result)

    def test_not_found_returns_empty_list(self):
        import zepto_client
        with patch.object(zepto_client, '_setup_context', return_value=("sess123", set())):
            with patch.object(zepto_client, '_mcp_tool', return_value="No products found"):
                result = zepto_client.search_all_items("tok", ["unicorn_item_xyz"])
        self.assertEqual(result["unicorn_item_xyz"], [])

    def test_network_error_returns_empty_not_raise(self):
        import zepto_client
        with patch.object(zepto_client, '_setup_context', return_value=("sess123", set())):
            with patch.object(zepto_client, '_mcp_tool', side_effect=Exception("connection refused")):
                result = zepto_client.search_all_items("tok", ["milk"])
        self.assertEqual(result["milk"], [])

    def test_aggregate_timeout_respected(self):
        import zepto_client, time as _time
        def slow_search(*a, **kw):
            _time.sleep(5)
            return ""
        with patch.object(zepto_client, '_AGGREGATE_TIMEOUT', 1):
            with patch.object(zepto_client, '_setup_context', return_value=("sess123", set())):
                with patch.object(zepto_client, '_mcp_tool', side_effect=slow_search):
                    start = _time.monotonic()
                    result = zepto_client.search_all_items("tok", ["milk"])
                    elapsed = _time.monotonic() - start
        self.assertLess(elapsed, 3)
        self.assertEqual(result["milk"], [])


# ── Unit: db.py Zepto helpers ───────────────────────────────────────────────

class TestDbZeptoHelpers(unittest.TestCase):
    """TC-12–TC-16: DB helper functions for Zepto."""

    def setUp(self):
        import db
        db._invalidate_types_cache()

    def test_store_and_retrieve_token(self):
        import db
        db.store_zepto_token(b"encrypted_blob_bytes")
        result = db.get_zepto_token()
        self.assertEqual(result, b"encrypted_blob_bytes")

    def test_delete_token(self):
        import db
        db.store_zepto_token(b"encrypted_blob_bytes")
        db.delete_zepto_token()
        self.assertIsNone(db.get_zepto_token())

    def test_create_and_consume_pending_op(self):
        import db
        items = [{"query": "milk", "selected_product": {"id": "p1"}, "quantity": 1}]
        token = db.create_pending_cart_op(items)
        self.assertIsNotNone(token)
        retrieved = db.consume_pending_cart_op(token)
        self.assertEqual(retrieved, items)

    def test_consume_deletes_token(self):
        import db
        items = [{"query": "eggs"}]
        token = db.create_pending_cart_op(items)
        db.consume_pending_cart_op(token)
        second = db.consume_pending_cart_op(token)
        self.assertIsNone(second)

    def test_consume_expired_token_returns_none(self):
        import db
        items = [{"query": "onions"}]
        token = db.create_pending_cart_op(items)
        # Manually expire it
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE pending_cart_ops SET expires_at = datetime('now', '-1 minute') WHERE token = ?",
                (token,)
            )
        result = db.consume_pending_cart_op(token)
        self.assertIsNone(result)


# ── Unit: classifier disambiguation ─────────────────────────────────────────

class TestShoppingListDisambiguation(unittest.TestCase):
    """TC-17–TC-20: classifier rules for shopping_list vs reminder."""

    def test_system_prompt_contains_disambiguation_rule(self):
        """TC-17: _SYSTEM prompt includes ≥2 commerce items rule."""
        import classifier
        self.assertIn("shopping_list", classifier._SYSTEM)
        self.assertIn("commerce", classifier._SYSTEM)

    def test_system_prompt_contains_quantity_token_rule(self):
        """TC-18: _SYSTEM prompt mentions quantity-token disambiguation."""
        import classifier
        self.assertIn("quantity-token", classifier._SYSTEM)

    def test_shopping_list_vs_reminder_rule_documented(self):
        """TC-19: disambiguation covers single-item occasion case."""
        import classifier
        self.assertIn("single item", classifier._SYSTEM)

    def test_extract_shopping_items_returns_structured_list(self):
        """TC-20: extract_shopping_items uses Haiku and returns structured items."""
        import classifier
        classifier.client = MagicMock()
        classifier.client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps({
                "items": [
                    {"name": "milk", "quantity": "2 L", "notes": None},
                    {"name": "eggs", "quantity": "12", "notes": "free-range"},
                ]
            }))]
        )
        items = classifier.extract_shopping_items("2L milk and a dozen eggs free-range")
        # Verify Haiku model was used (cheaper than Opus for text extraction)
        call_kwargs = classifier.client.messages.create.call_args
        self.assertEqual(call_kwargs[1].get('model') or call_kwargs[0][0], classifier.HAIKU_MODEL)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "milk")


# ── Security: token bypass tests ────────────────────────────────────────────

class TestConfirmationTokenSecurity(unittest.TestCase):
    """TC-21–TC-25: confirmation_token bypass protection."""

    def setUp(self):
        from cryptography.fernet import Fernet
        self.fernet_key = Fernet.generate_key().decode()
        import zepto_client, db, app as flask_app
        # Store an encrypted token using a fresh Fernet key
        with patch.object(zepto_client, 'FERNET_KEY', self.fernet_key):
            ct = zepto_client.encrypt_token("test_access_token")
        db.store_zepto_token(ct)
        # Patch FERNET_KEY on the module so decrypt calls use the same key
        self._fernet_patcher = patch.object(zepto_client, 'FERNET_KEY', self.fernet_key)
        self._fernet_patcher.start()
        flask_app.app.config['TESTING'] = True
        self.client = flask_app.app.test_client()

    def tearDown(self):
        self._fernet_patcher.stop()

    def test_cart_add_no_token_returns_403(self):
        """TC-21: POST /api/zepto/cart-add with no confirmation_token → 403."""
        resp = self.client.post('/api/zepto/cart-add',
                                json={},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_cart_add_fabricated_uuid_returns_403(self):
        """TC-22: POST /api/zepto/cart-add with random UUID not in DB → 403."""
        fake_token = str(uuid.uuid4())
        resp = self.client.post('/api/zepto/cart-add',
                                json={"confirmation_token": fake_token},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_cart_add_expired_token_returns_403(self):
        """TC-23: Expired confirmation_token → 403."""
        import db
        items = [{"query": "milk", "selected_product": {"id": "p1"}, "quantity": 1}]
        token = db.create_pending_cart_op(items)
        # Manually expire
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE pending_cart_ops SET expires_at = datetime('now', '-1 minute') WHERE token = ?",
                (token,)
            )
        resp = self.client.post('/api/zepto/cart-add',
                                json={"confirmation_token": token},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_cart_add_token_single_use_replay_returns_403(self):
        """TC-24: Token replay after successful use → 403 on second call."""
        import db
        items = [{"query": "milk", "selected_product": {"pvid": "11111111-1111-1111-1111-111111111111", "spid": "22222222-2222-2222-2222-222222222222"}, "quantity": 1}]
        token = db.create_pending_cart_op(items)

        with patch('app.add_items_to_cart', return_value="Cart updated"):
            resp1 = self.client.post('/api/zepto/cart-add',
                                     json={"confirmation_token": token},
                                     content_type='application/json')
        # First call: token consumed. Second call must be 403 regardless.
        resp2 = self.client.post('/api/zepto/cart-add',
                                 json={"confirmation_token": token},
                                 content_type='application/json')
        self.assertEqual(resp2.status_code, 403)

    def test_zepto_search_without_connection_returns_401(self):
        """TC-25: Search without Zepto connected → 401."""
        import db
        db.delete_zepto_token()  # ensure no token
        resp = self.client.post('/api/zepto/search',
                                json={"capture_id": 99999},
                                content_type='application/json')
        # 401 = not connected (no capture_id check happens before auth check)
        self.assertIn(resp.status_code, [400, 401])


class TestTokenSecrecyInResponses(unittest.TestCase):
    """TC-26–TC-28: access_token never appears in API responses or logs."""

    def setUp(self):
        from cryptography.fernet import Fernet
        self.fernet_key = Fernet.generate_key().decode()
        import zepto_client, db, app as flask_app
        with patch.object(zepto_client, 'FERNET_KEY', self.fernet_key):
            ct = zepto_client.encrypt_token("SUPER_SECRET_ACCESS_TOKEN")
        db.store_zepto_token(ct)
        self._fernet_patcher = patch.object(zepto_client, 'FERNET_KEY', self.fernet_key)
        self._fernet_patcher.start()
        flask_app.app.config['TESTING'] = True
        self.client = flask_app.app.test_client()

    def tearDown(self):
        self._fernet_patcher.stop()

    def test_zepto_status_response_has_no_access_token(self):
        """TC-26: /api/zepto/status does not leak access_token."""
        resp = self.client.get('/api/zepto/status')
        body = resp.data.decode()
        self.assertNotIn("SUPER_SECRET_ACCESS_TOKEN", body)
        self.assertNotIn("access_token", body.lower().replace("connected", ""))

    def test_token_stored_as_bytes_not_plaintext(self):
        """TC-27: access_token column in DB is encrypted bytes, not readable text."""
        import db, sqlite3
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT access_token FROM external_credentials WHERE service='zepto'"
            ).fetchone()
        raw_bytes = bytes(row["access_token"])
        self.assertNotIn(b"SUPER_SECRET_ACCESS_TOKEN", raw_bytes)

    def test_search_response_has_no_access_token(self):
        """TC-28: /api/zepto/search response does not contain access_token."""
        import db
        capture_id = db.insert_capture(
            raw_input="milk and eggs",
            content_type="shopping_list",
            confidence=0.92,
            rationale="test",
            metadata={"items": [{"name": "milk"}, {"name": "eggs"}]},
            tags=[],
        )
        with patch('app.search_all_items', return_value={"milk": SAMPLE_PRODUCTS, "eggs": []}):
            resp = self.client.post('/api/zepto/search',
                                    json={"capture_id": capture_id},
                                    content_type='application/json')
        body = resp.data.decode()
        self.assertNotIn("SUPER_SECRET_ACCESS_TOKEN", body)


# ── Code Inspection ──────────────────────────────────────────────────────────

class TestCodeInspection(unittest.TestCase):
    """TC-34–TC-35: Static checks on source code."""

    def _get_python_sources(self):
        root = os.path.dirname(os.path.dirname(__file__))
        sources = []
        for fname in ['app.py', 'zepto_client.py', 'db.py', 'classifier.py', 'config.py']:
            fpath = os.path.join(root, fname)
            if os.path.exists(fpath):
                with open(fpath) as f:
                    sources.append((fname, f.read()))
        return sources

    def test_order_placement_never_called(self):
        """TC-34 (M-5 hard zero): 'order_placement' must never appear as a callable tool name."""
        import re
        # Match any _mcp_call invocation or JSON-RPC tool name using "order_placement"
        pattern = re.compile(r'_mcp_call\s*\([^)]*order_placement|"name"\s*:\s*"order_placement"')
        for fname, content in self._get_python_sources():
            matches = pattern.findall(content)
            self.assertEqual(
                matches, [],
                msg=f"'order_placement' found as callable tool in {fname} — M-5 violation: {matches}"
            )

    def test_fernet_key_not_hardcoded(self):
        """TC-35: FERNET_KEY must not be hardcoded — must come from env."""
        for fname, content in self._get_python_sources():
            # Should not see a raw Fernet key (32 bytes base64url = 44 chars ending in '=')
            import re
            hardcoded = re.findall(r'[A-Za-z0-9_-]{43}=', content)
            for match in hardcoded:
                # Exclude known non-key patterns (UUIDs, test strings)
                self.fail(
                    f"Possible hardcoded Fernet key in {fname}: {match[:10]}…"
                ) if len(match) == 44 else None


# ── Integration: API routes ──────────────────────────────────────────────────

class TestZeptoApiRoutes(unittest.TestCase):
    """TC-29–TC-33: End-to-end route tests with mocked Zepto MCP."""

    def setUp(self):
        from cryptography.fernet import Fernet
        self.fernet_key = Fernet.generate_key().decode()
        import zepto_client, db, app as flask_app
        db.delete_zepto_token()
        self._fernet_patcher = patch.object(zepto_client, 'FERNET_KEY', self.fernet_key)
        self._fernet_patcher.start()
        flask_app.app.config['TESTING'] = True
        self.client = flask_app.app.test_client()
        self.zepto_client = zepto_client

    def tearDown(self):
        self._fernet_patcher.stop()

    def test_status_not_connected(self):
        """TC-29: status returns connected=False when no token stored."""
        resp = self.client.get('/api/zepto/status')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertFalse(data['connected'])

    def test_status_connected(self):
        """TC-30: status returns connected=True when token stored."""
        import db
        db.store_zepto_token(self.zepto_client.encrypt_token("tok"))
        resp = self.client.get('/api/zepto/status')
        data = json.loads(resp.data)
        self.assertTrue(data['connected'])

    def test_search_returns_confirmation_token(self):
        """TC-31: search returns confirmation_token when items found."""
        import db
        db.store_zepto_token(self.zepto_client.encrypt_token("tok"))
        cid = db.insert_capture(
            raw_input="buy milk", content_type="shopping_list",
            confidence=0.9, rationale="test",
            metadata={"items": [{"name": "milk"}]}, tags=[],
        )
        with patch('app.search_all_items', return_value={"milk": SAMPLE_PRODUCTS}):
            resp = self.client.post('/api/zepto/search',
                                    json={"capture_id": cid},
                                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("confirmation_token", data)
        self.assertIsNotNone(data["confirmation_token"])

    def test_cart_add_valid_token_calls_mcp(self):
        """TC-32: Valid confirmation_token triggers update_cart MCP call."""
        import db
        db.store_zepto_token(self.zepto_client.encrypt_token("tok"))
        items = [{"query": "milk", "selected_product": {"pvid": "11111111-1111-1111-1111-111111111111", "spid": "22222222-2222-2222-2222-222222222222"}, "quantity": 2}]
        token = db.create_pending_cart_op(items)

        with patch('app.add_items_to_cart', return_value="Cart updated"):
            resp = self.client.post('/api/zepto/cart-add',
                                    json={"confirmation_token": token},
                                    content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["added"]), 1)

    def test_disconnect_removes_token(self):
        """TC-33: POST /api/zepto/disconnect removes the token."""
        import db
        db.store_zepto_token(self.zepto_client.encrypt_token("tok"))
        resp = self.client.post('/api/zepto/disconnect')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(db.get_zepto_token())


# ── Shopping list card ──────────────────────────────────────────────────────

class TestShoppingListCard(unittest.TestCase):
    """TC-36: shopping_list card has correct display and actions."""

    def test_shopping_list_actions_include_zepto_search(self):
        import db
        cid = db.insert_capture(
            raw_input="milk, eggs, onions",
            content_type="shopping_list",
            confidence=0.91,
            rationale="test",
            metadata={"items": [{"name": "milk"}, {"name": "eggs"}, {"name": "onions"}], "title": "Test list"},
            tags=["grocery"],
        )
        card = db.get_capture(cid)
        self.assertIn("zepto_search", card["display"]["actions"])
        self.assertEqual(card["type"], "shopping_list")

    def test_shopping_list_display_shows_item_names(self):
        import db
        cid = db.insert_capture(
            raw_input="milk and eggs",
            content_type="shopping_list",
            confidence=0.91,
            rationale="test",
            metadata={"items": [{"name": "milk"}, {"name": "eggs"}]},
            tags=[],
        )
        card = db.get_capture(cid)
        subtitle = card["display"]["subtitle"]
        self.assertIn("milk", subtitle)
        self.assertIn("eggs", subtitle)


class TestParseCartItems(unittest.TestCase):
    """TC-XX: _parse_cart_items parses view_cart text correctly."""

    CART_TEXT = (
        "🛒 Cart Items (2 items)\n"
        "      [SYSTEM NOTE: Product IDs below are for cart operations]\n\n"
        "      1. Country Delight Natural Fresh Cow Milk | Pouch - ₹54 (Qty: 1)\n"
        "   pvid: f1f1d95f-ada9-48f7-ab10-f094bb40337b, spid: 1e4af3f6-c0ac-5593-8b96-c835abafd1b2\n"
        "2. Akshayakalpa Amrutha - A2 Farm Organic Cow Fresh Milk | Pouch - ₹53 (Qty: 2)\n"
        "   pvid: 0d2d70a4-1469-45a3-b1c4-4ffe692f86ae, spid: 63afcfbb-1093-49a1-9801-be93d06aa69c\n"
    )

    def test_parses_item_count(self):
        import zepto_client
        items = zepto_client._parse_cart_items(self.CART_TEXT)
        self.assertEqual(len(items), 2)

    def test_parses_name_price_qty(self):
        import zepto_client
        items = zepto_client._parse_cart_items(self.CART_TEXT)
        self.assertIn("Country Delight", items[0]["name"])
        self.assertEqual(items[0]["price"], 54.0)
        self.assertEqual(items[0]["qty"], 1)
        self.assertEqual(items[1]["qty"], 2)

    def test_parses_pvid_spid(self):
        import zepto_client
        items = zepto_client._parse_cart_items(self.CART_TEXT)
        self.assertEqual(items[0]["pvid"], "f1f1d95f-ada9-48f7-ab10-f094bb40337b")
        self.assertEqual(items[0]["spid"], "1e4af3f6-c0ac-5593-8b96-c835abafd1b2")
        self.assertEqual(items[1]["pvid"], "0d2d70a4-1469-45a3-b1c4-4ffe692f86ae")

    def test_empty_cart_returns_empty_list(self):
        import zepto_client
        items = zepto_client._parse_cart_items("🛒 Cart is empty")
        self.assertEqual(items, [])

    def test_cart_total_calculated(self):
        import zepto_client
        items = zepto_client._parse_cart_items(self.CART_TEXT)
        total = sum(i["price"] * i["qty"] for i in items)
        # 54*1 + 53*2 = 160
        self.assertAlmostEqual(total, 160.0)


class TestViewCartRoute(unittest.TestCase):
    """TC-XX: /api/zepto/cart endpoint."""

    def setUp(self):
        import app as flask_app
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()

    @patch("app.db.get_zepto_token", return_value=None)
    def test_cart_returns_401_when_not_connected(self, _):
        resp = self.client.get("/api/zepto/cart")
        self.assertEqual(resp.status_code, 401)

    @patch("app.get_cart")
    @patch("app.decrypt_token", return_value="fake-token")
    @patch("app.db.get_zepto_token", return_value=b"enc")
    def test_cart_returns_items(self, _, __, mock_get_cart):
        mock_get_cart.return_value = {
            "items": [{"name": "Milk", "price": 54.0, "qty": 1, "pvid": "aaa", "spid": "bbb"}],
            "total": 54.0,
            "count": 1,
        }
        resp = self.client.get("/api/zepto/cart")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["name"], "Milk")
        self.assertAlmostEqual(data["total"], 54.0)


class TestParsePastOrdersFull(unittest.TestCase):
    """TC-XX: _parse_past_orders_full extracts name + count and sorts by count desc."""

    PAST_TEXT = (
        "Past order items:\n"
        "1. Heritage Toned Fresh Milk | Pouch (ordered in 8 orders)\n"
        "2. Country Delight Natural Fresh Cow Milk | Pouch (ordered in 3 orders)\n"
        "3. Amul Taaza Toned Fresh Milk (ordered in 1 order)\n"
    )

    def test_parses_count(self):
        import zepto_client
        items = zepto_client._parse_past_orders_full(self.PAST_TEXT)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["count"], 8)
        self.assertEqual(items[1]["count"], 3)
        self.assertEqual(items[2]["count"], 1)

    def test_sorted_by_count_desc(self):
        import zepto_client
        items = zepto_client._parse_past_orders_full(self.PAST_TEXT)
        counts = [i["count"] for i in items]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_parses_name(self):
        import zepto_client
        items = zepto_client._parse_past_orders_full(self.PAST_TEXT)
        self.assertIn("Heritage", items[0]["name"])

    def test_empty_text_returns_empty_list(self):
        import zepto_client
        items = zepto_client._parse_past_orders_full("No past orders.")
        self.assertEqual(items, [])


class TestAutoAddEndpoint(unittest.TestCase):
    """TC-XX: POST /api/zepto/auto-add endpoint."""

    def setUp(self):
        import app as flask_app
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()

    @patch("app.db.get_zepto_token", return_value=None)
    def test_returns_401_when_not_connected(self, _):
        resp = self.client.post("/api/zepto/auto-add",
                                json={"tokens": ["milk"]},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    @patch("app.db.get_zepto_token", return_value=None)
    def test_returns_400_with_empty_tokens(self, _):
        # Even if token existed, empty tokens should 400 — but 401 fires first here
        resp = self.client.post("/api/zepto/auto-add",
                                json={"tokens": []},
                                content_type="application/json")
        self.assertIn(resp.status_code, (400, 401))

    @patch("app.auto_add_shopping_items")
    @patch("app.db.archive_capture")
    @patch("app.db.log_event")
    @patch("app.decrypt_token", return_value="fake-token")
    @patch("app.db.get_zepto_token", return_value=b"enc")
    def test_archives_capture_on_success(self, _, __, _log, mock_archive, mock_auto_add):
        mock_auto_add.return_value = [
            {"token": "milk", "product_name": "Heritage Milk", "added": True, "error": None}
        ]
        resp = self.client.post("/api/zepto/auto-add",
                                json={"tokens": ["milk"], "capture_id": 99},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["archived"])
        mock_archive.assert_called_once_with(99)

    @patch("app.auto_add_shopping_items")
    @patch("app.db.log_event")
    @patch("app.decrypt_token", return_value="fake-token")
    @patch("app.db.get_zepto_token", return_value=b"enc")
    def test_does_not_archive_when_nothing_added(self, _, __, _log, mock_auto_add):
        mock_auto_add.return_value = [
            {"token": "xyz", "product_name": None, "added": False, "error": "Not found"}
        ]
        resp = self.client.post("/api/zepto/auto-add",
                                json={"tokens": ["xyz"], "capture_id": 100},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertFalse(data["archived"])


class TestFeedArchivedEndpoint(unittest.TestCase):
    """TC-XX: GET /api/feed/archived endpoint."""

    def setUp(self):
        import app as flask_app
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()

    @patch("app.db.get_archived_captures", return_value=[])
    def test_returns_empty_list_when_no_archived(self, _):
        resp = self.client.get("/api/feed/archived")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["cards"], [])

    @patch("app.db.get_archived_captures")
    def test_returns_archived_cards(self, mock_get):
        mock_get.return_value = [{"id": 1, "type": "shopping_list", "archived": True}]
        resp = self.client.get("/api/feed/archived")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["cards"]), 1)
        self.assertTrue(data["cards"][0]["archived"])


class TestWordOverlapScore(unittest.TestCase):
    """Deterministic fuzzy-match helper."""

    def test_identical_names_score_one(self):
        import zepto_client
        score = zepto_client._word_overlap_score(
            "Heritage Toned Fresh Milk | Pouch",
            "Heritage Toned Fresh Milk | Pouch",
        )
        self.assertAlmostEqual(score, 1.0)

    def test_different_brands_score_low(self):
        import zepto_client
        # "Nandini" vs "Heritage" — only "toned" and "milk" might overlap
        score = zepto_client._word_overlap_score(
            "Nandini Toned Milk | Pouch",
            "Heritage Toned Milk | Pouch",
        )
        # "toned" and "milk" overlap (2/2 meaningful non-stop words in name_b)
        # "heritage" not in name_a → fraction depends on stop filtering
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_unrelated_products_score_zero(self):
        import zepto_client
        score = zepto_client._word_overlap_score(
            "Maggi Masala Noodles 70g",
            "Heritage Toned Milk | Pouch",
        )
        self.assertAlmostEqual(score, 0.0)

    def test_empty_past_order_returns_zero(self):
        import zepto_client
        score = zepto_client._word_overlap_score("Milk Product", "")
        self.assertAlmostEqual(score, 0.0)

    def test_same_brand_partial_match(self):
        import zepto_client
        # "Amul Milk" (past) vs "Amul Taaza Toned Milk" (search) — both have "amul" and "milk"
        score = zepto_client._word_overlap_score(
            "Amul Taaza Toned Milk",
            "Amul Milk",
        )
        # name_b tokens: {amul, milk} — both present in name_a → 2/2 = 1.0
        self.assertAlmostEqual(score, 1.0)


class TestDeterministicBestMatch(unittest.TestCase):
    """_deterministic_best_match returns highest-frequency past-order match."""

    def _make_product(self, name, pvid=None):
        return {"name": name, "price": "50", "size": "1 L",
                "pvid": pvid or "aaa", "spid": "bbb", "previously_bought": False}

    def test_returns_negative_one_when_no_past_orders(self):
        import zepto_client
        products = [self._make_product("Heritage Toned Milk | Pouch")]
        idx = zepto_client._deterministic_best_match(products, [])
        self.assertEqual(idx, -1)

    def test_returns_matching_product_index(self):
        import zepto_client
        products = [
            self._make_product("Nandini Toned Milk | Pouch", pvid="nnd"),
            self._make_product("Heritage Toned Milk | Pouch", pvid="her"),
        ]
        past = [{"name": "Heritage Toned Milk | Pouch", "count": 8}]
        idx = zepto_client._deterministic_best_match(products, past)
        # Heritage is product index 1
        self.assertEqual(idx, 1)

    def test_prefers_highest_frequency_match(self):
        """Regression: 'milk' → must pick the most-ordered milk, not the first result."""
        import zepto_client
        products = [
            self._make_product("Nandini Toned Fresh Milk | Pouch", pvid="nan"),   # first in search
            self._make_product("Heritage Toned Fresh Milk | Pouch", pvid="her"),  # second
        ]
        past = [
            {"name": "Heritage Toned Fresh Milk | Pouch", "count": 8},  # highest
            {"name": "Nandini Toned Fresh Milk | Pouch", "count": 2},
        ]
        idx = zepto_client._deterministic_best_match(products, past)
        # Must pick Heritage (idx=1), not Nandini (idx=0)
        self.assertEqual(idx, 1)
        self.assertIn("Heritage", products[idx]["name"])

    def test_returns_negative_one_when_no_overlap(self):
        import zepto_client
        products = [self._make_product("Milk Product 1L")]
        past = [{"name": "Maggi Masala Noodles", "count": 10}]
        idx = zepto_client._deterministic_best_match(products, past)
        self.assertEqual(idx, -1)


if __name__ == "__main__":
    unittest.main()
