"""
Zepto MCP HTTP client for CORTEX.
Transport: MCP Streamable HTTP (SSE).
Each public operation creates a fresh MCP session internally.
M-5 hard zero: the MCP tools that place real orders are never invoked here.
"""
import json
import re
import time
import uuid

import anthropic
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from cryptography.fernet import Fernet, InvalidToken

from config import FERNET_KEY, HAIKU_MODEL, ZEPTO_MCP_URL

_CALL_TIMEOUT = 10       # seconds per MCP call
_AGGREGATE_TIMEOUT = 20  # seconds for parallel search_all_items
_MAX_WORKERS = 5
_DEVICE_ID = "cortex-mcp-client-v1"


# ── Fernet encrypt / decrypt ──────────────────────────────────────────────────

def _get_fernet():
    if not FERNET_KEY:
        raise ValueError("FERNET_KEY not set — Zepto integration unavailable")
    key = FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY
    return Fernet(key)


def encrypt_token(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def decrypt_token(ciphertext: bytes) -> str:
    try:
        return _get_fernet().decrypt(ciphertext).decode()
    except InvalidToken:
        raise ValueError("Token decryption failed — invalid or tampered ciphertext")


# ── MCP transport ─────────────────────────────────────────────────────────────

def _headers(token, session_id=None):
    h = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h


_SSE_FIELD_PREFIXES = ("event:", "id:", "retry:", ":")


def _sse_parse(resp):
    """
    Parse an SSE HTTP response. Returns the first JSON-RPC object with 'result' or 'error'.

    Zepto's MCP server embeds literal newlines inside JSON string values (invalid JSON /
    invalid SSE). Standard line-by-line parsing breaks because the blank lines that terminate
    SSE events also appear inside JSON strings (e.g. address text with paragraph breaks).

    Fix: use brace-counting to extract the complete JSON object from the raw response text,
    then repair embedded literal newlines before parsing.
    """
    text = resp.content.decode("utf-8", errors="replace")

    # Find the start of the JSON object — scan for first '{' after a 'data:' marker
    data_pos = text.find("data:")
    if data_pos == -1:
        return {}
    obj_start = text.find("{", data_pos + 5)
    if obj_start == -1:
        return {}

    # Walk forward counting braces to find the end of the JSON object.
    # Track string context so braces inside strings are ignored.
    depth = 0
    in_str = False
    esc = False
    end_pos = -1
    for i in range(obj_start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\" and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue        # skip everything inside strings (including \n, \r)
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break

    if end_pos == -1:
        return {}

    json_str = text[obj_start:end_pos]

    # First try: parse as-is (works when newlines are properly escaped as \n)
    try:
        obj = json.loads(json_str)
        if "result" in obj or "error" in obj:
            return obj
    except Exception:
        pass

    # Second try: Zepto embeds literal \x0a / \x0d inside JSON strings.
    # Replace them with their JSON escape equivalents and retry.
    try:
        fixed = json_str.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
        obj = json.loads(fixed)
        if "result" in obj or "error" in obj:
            return obj
    except Exception:
        pass

    return {}


def _mcp_initialize(token):
    """Create a new MCP session. Returns session_id string."""
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "CORTEX", "version": "1.0"},
        },
    }
    resp = requests.post(ZEPTO_MCP_URL, json=payload, headers=_headers(token), timeout=_CALL_TIMEOUT)
    resp.raise_for_status()
    session_id = resp.headers.get("Mcp-Session-Id")
    if not session_id:
        raise ValueError("MCP initialize did not return Mcp-Session-Id")
    return session_id


def _mcp_tool(token, session_id, tool_name, arguments):
    """
    Call a single MCP tool. Returns the content[0].text string.
    Raises ValueError on MCP-level errors.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    resp = requests.post(
        ZEPTO_MCP_URL, json=payload,
        headers=_headers(token, session_id),
        timeout=_CALL_TIMEOUT,
    )
    resp.raise_for_status()
    body = _sse_parse(resp)
    if "error" in body:
        raise ValueError(f"MCP error: {body['error'].get('message', str(body['error']))}")
    result = body.get("result", {})
    if result.get("isError"):
        text = (result.get("content") or [{}])[0].get("text", "Unknown tool error")
        raise ValueError(f"Tool error: {text[:200]}")
    content = result.get("content", [])
    return content[0].get("text", "") if content else ""


# ── Session setup ─────────────────────────────────────────────────────────────

# Regex for address ID lines: Zepto uses straight ASCII double-quotes around labels.
_ADDR_RE = re.compile(
    r'"([^"]+)".{1,30}ID:\s*([a-f0-9-]{36})',
    re.IGNORECASE,
)
# "1. Home New Blr: Flat 203, 2nd Floor …"
_ADDR_ITEM_RE = re.compile(r"^\d+\.\s+(.+?):\s+(.+)$")
# '1. "Home New Blr" — ID: <uuid>' (em-dash may be mangled)
_ADDR_ID_RE   = re.compile(r'^\d+\.\s+"([^"]+)".{0,10}ID:\s*([a-f0-9-]{36})', re.IGNORECASE)


def _find_home_address_id(text):
    """Return the ID of the first 'Home'-labelled address, or the first address found."""
    addresses = _ADDR_RE.findall(text)
    for name, addr_id in addresses:
        if "home" in name.lower():
            return addr_id
    return addresses[0][1] if addresses else None


def _parse_address_list(text):
    """
    Parse list_saved_addresses text into [{id, name, address}].
    Matches numbered items before --- against the ID section below ---.
    """
    parts = text.split("---", 1)
    list_section = parts[0]
    id_section   = parts[1] if len(parts) > 1 else ""

    items = []
    for line in list_section.splitlines():
        m = _ADDR_ITEM_RE.match(line.strip())
        if m:
            items.append({"name": m.group(1).strip(), "address": m.group(2).strip(), "id": ""})

    idx = 0
    for line in id_section.splitlines():
        m = _ADDR_ID_RE.match(line.strip())
        if m and idx < len(items):
            items[idx]["id"] = m.group(2)
            idx += 1

    return [a for a in items if a["id"]]


def _setup_context(token, address_id=None):
    """
    Full session setup:
      initialize → list saved addresses → select address (provided or home default)
      → get_past_order_items (mandatory before any search)
    Returns (session_id, past_product_names set).
    """
    session_id = _mcp_initialize(token)

    addr_text = _mcp_tool(token, session_id, "list_saved_addresses", {})
    if not address_id:
        address_id = _find_home_address_id(addr_text)
    if not address_id:
        raise ValueError("No saved addresses found in Zepto account")

    _mcp_tool(token, session_id, "select_saved_address", {"addressId": address_id})

    past_text = _mcp_tool(token, session_id, "get_past_order_items", {})
    past_names = _parse_past_order_names(past_text)

    return session_id, past_names


def _setup_for_cart(token, address_id=None, need_past_orders=False):
    """Lightweight session setup for cart operations (no parallel search needed).
    need_past_orders: pass True only when past-order data is used (search/auto-add).
    Pure cart reads/writes skip get_past_order_items to reduce latency and failure surface.
    """
    session_id = _mcp_initialize(token)
    addr_text = _mcp_tool(token, session_id, "list_saved_addresses", {})
    if not address_id:
        address_id = _find_home_address_id(addr_text)
    if address_id:
        _mcp_tool(token, session_id, "select_saved_address", {"addressId": address_id})
    if need_past_orders:
        _mcp_tool(token, session_id, "get_past_order_items", {})
    return session_id


# ── Response text parsers ─────────────────────────────────────────────────────

# "1. Country Delight Natural Fresh Cow Milk | Pouch - ₹54 (Qty: 1)"
_CART_ITEM_RE = re.compile(
    r"^\d+\.\s+(.+?)\s+-\s+[^\d]*([\d.]+)\s+\(Qty:\s*(\d+)\)",
)
# "   pvid: <uuid>, spid: <uuid>"
_CART_ID_RE = re.compile(
    r"pvid:\s*([a-f0-9-]{36}),\s*spid:\s*([a-f0-9-]{36})",
    re.IGNORECASE,
)

# "1. Heritage Toned Fresh Milk | Pouch - ₹26 (1 pack (500 ml))"
_PRODUCT_LINE_RE = re.compile(
    r"^\d+\.\s+(.+?)\s+-\s+[^\d]*([\d.]+)\s+\((.+?)\)\s*$"
)
# "[1] pvid: uuid, spid: uuid"
_ID_LINE_RE = re.compile(
    r"^\[(\d+)\]\s+pvid:\s+([a-f0-9-]{36}),\s+spid:\s+([a-f0-9-]{36})",
    re.IGNORECASE,
)
# "1. Product Name (ordered in N orders)"
_PAST_RE = re.compile(r"^\d+\.\s+(.+?)\s+\(ordered in")
# Same but also captures the order count
_PAST_FULL_RE = re.compile(r"^\d+\.\s+(.+?)\s+\(ordered in (\d+)", re.IGNORECASE)

# Words too generic/unit-like to be brand signals
_OVERLAP_STOP = frozenset({
    "pack", "pouch", "litre", "liter", "grams", "each", "with", "from", "made",
    "best", "only", "fresh", "pure",
})


def _parse_product_list(text):
    """
    Parse search_products text response.
    Returns list of dicts: {name, price, size, pvid, spid}.
    Only products with valid pvid/spid are returned.
    """
    products = []
    ids_by_idx = {}

    parts = text.split("---", 1)
    product_section = parts[0]
    id_section = parts[1] if len(parts) > 1 else ""

    for line in product_section.splitlines():
        m = _PRODUCT_LINE_RE.match(line.strip())
        if m:
            products.append({
                "name": m.group(1).strip(),
                "price": m.group(2),
                "size": m.group(3).strip(),
                "pvid": "",
                "spid": "",
                "previously_bought": False,
            })

    for line in id_section.splitlines():
        m = _ID_LINE_RE.match(line.strip())
        if m:
            idx = int(m.group(1)) - 1  # to 0-indexed
            if 0 <= idx < len(products):
                products[idx]["pvid"] = m.group(2)
                products[idx]["spid"] = m.group(3)

    return [p for p in products if p["pvid"]]


def _parse_past_order_names(text):
    """Extract product names from get_past_order_items text. Returns lowercase set."""
    names = set()
    for line in text.splitlines():
        m = _PAST_RE.match(line.strip())
        if m:
            names.add(m.group(1).strip().lower())
    return names


def _word_overlap_score(name_a: str, name_b: str) -> float:
    """
    Fraction of significant words in name_b that also appear in name_a.
    'Significant' = length > 3 and not in _OVERLAP_STOP.
    Used to fuzzy-match a search-result product against a past-order name.
    """
    def _tokens(s):
        return {
            w for w in re.sub(r"[^a-z0-9]", " ", s.lower()).split()
            if len(w) > 3 and w not in _OVERLAP_STOP
        }
    ta = _tokens(name_a)
    tb = _tokens(name_b)
    if not tb:
        return 0.0
    return len(ta & tb) / len(tb)


def _deterministic_best_match(products, past_orders, threshold: float = 0.5) -> int:
    """
    Score every (product, past_order) pair: overlap_score × order_count.
    Returns the 0-based index of the best-matching product, or -1 if no pair
    exceeds the overlap threshold.  Deterministic — no LLM call.
    """
    if not past_orders:
        return -1
    best_idx = -1
    best_score = 0.0
    for pi, product in enumerate(products):
        for po in past_orders:
            overlap = _word_overlap_score(product["name"], po["name"])
            if overlap >= threshold:
                score = overlap * po["count"]
                if score > best_score:
                    best_score = score
                    best_idx = pi
    return best_idx


def _parse_past_orders_full(text):
    """Parse get_past_order_items into [{name, count}], sorted by count desc."""
    items = []
    for line in text.splitlines():
        m = _PAST_FULL_RE.match(line.strip())
        if m:
            items.append({"name": m.group(1).strip(), "count": int(m.group(2))})
    items.sort(key=lambda x: -x["count"])
    return items


def _llm_select_product(search_results, past_orders):
    """
    Pick the best product from search_results using past order frequency.

    Step 1 — deterministic: word-overlap × order-count. If any product scores
    above the threshold, return it immediately (no LLM cost, no hallucination).
    Step 2 — Haiku fallback: only runs when no confident past-order match exists.
    The prompt is hard-constrained ("MUST pick matching product") rather than soft.
    """
    if not search_results:
        return None
    if len(search_results) == 1:
        return search_results[0]

    # Deterministic pre-selection: prefer products matching past order names
    det_idx = _deterministic_best_match(search_results, past_orders)
    if det_idx >= 0:
        return search_results[det_idx]

    # Haiku fallback — no confident past-order match found
    products_text = "\n".join(
        f"{i+1}. {p['name']} - ₹{p['price']} ({p['size']})"
        + (" [PREVIOUSLY BOUGHT]" if p.get("previously_bought") else "")
        for i, p in enumerate(search_results[:10])
    )
    past_text = (
        "\n".join(f"- {p['name']} (ordered {p['count']} time{'s' if p['count'] != 1 else ''})"
                  for p in past_orders[:20])
        or "No past orders available."
    )
    prompt = (
        f"Zepto search results:\n{products_text}\n\n"
        f"My past orders (most frequent first):\n{past_text}\n\n"
        f"RULE: If any search result is the SAME product (same brand + same product type) "
        f"as a past order, pick it — past-order match overrides everything. "
        f"Ignore partial word matches across different product categories "
        f"(e.g. 'Cadbury Dairy Milk' chocolate is NOT a match for dairy milk search results). "
        f"If no past-order match, pick the most standard/common option for a household. "
        f"Reply with only the number (1–{min(10, len(search_results))})."
    )
    try:
        msg = anthropic.Anthropic().messages.create(
            model=HAIKU_MODEL,
            max_tokens=8,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        m = re.search(r"\d+", raw)
        if m:
            idx = int(m.group()) - 1
            if 0 <= idx < len(search_results):
                return search_results[idx]
    except Exception:
        pass
    return search_results[0]


# ── Public API ────────────────────────────────────────────────────────────────

def list_all_addresses(access_token):
    """Return [{id, name, address}] for all saved Zepto addresses."""
    session_id = _mcp_initialize(access_token)
    text = _mcp_tool(access_token, session_id, "list_saved_addresses", {})
    return _parse_address_list(text)


def search_all_items(access_token, items, address_id=None):
    """
    Search all items in parallel.
    Returns {item_name: [product_dicts]} where each product has:
      name, price, size, pvid, spid, previously_bought
    Items with no results get an empty list.
    """
    session_id, past_names = _setup_context(access_token, address_id=address_id)
    results = {item: [] for item in items}

    def _search_one(item):
        try:
            text = _mcp_tool(access_token, session_id, "search_products", {"query": item})
            products = _parse_product_list(text)
            for p in products:
                p["previously_bought"] = p["name"].lower() in past_names
            return item, products
        except Exception:
            return item, []

    start = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=_MAX_WORKERS)
    try:
        futures = {pool.submit(_search_one, item): item for item in items}
        for future in list(futures.keys()):
            remaining = _AGGREGATE_TIMEOUT - (time.monotonic() - start)
            if remaining <= 0:
                break
            try:
                item_name, products = future.result(timeout=max(0.1, remaining))
                results[item_name] = products
            except (FuturesTimeoutError, Exception):
                pass
    finally:
        pool.shutdown(wait=False)

    return results


def add_items_to_cart(access_token, cart_items, address_id=None):
    """
    Add items to cart using update_cart MCP tool.
    Fetches the current cart first and merges new items in — update_cart replaces
    the cart entirely, so omitting existing items would wipe them.
    cart_items: list of {pvid, spid, quantity}
    M-5: order-placement tools are never called here.
    """
    if not cart_items:
        raise ValueError("No items to add to cart")

    session_id = _setup_for_cart(access_token, address_id=address_id)

    # Fetch existing cart items so we don't wipe them
    try:
        existing_text = _mcp_tool(access_token, session_id, "view_cart", {})
        existing = _parse_cart_items(existing_text)
    except Exception:
        existing = []

    # Build merged cart keyed by pvid
    merged = {
        item["pvid"]: {
            "productVariantId": item["pvid"],
            "storeProductId": item["spid"],
            "quantity": item["qty"],
        }
        for item in existing
        if item.get("pvid")
    }

    # Overlay new items — add to existing qty if pvid already in cart
    for item in cart_items:
        pvid = item.get("pvid", "")
        spid = item.get("spid", "")
        qty = int(item.get("quantity", 1))
        if not pvid or not spid:
            continue
        if pvid in merged:
            merged[pvid]["quantity"] += qty
        else:
            merged[pvid] = {"productVariantId": pvid, "storeProductId": spid, "quantity": qty}

    mcp_items = list(merged.values())
    if not mcp_items:
        raise ValueError("No valid pvid/spid pairs in cart items")

    return _mcp_tool(access_token, session_id, "update_cart", {
        "deviceId": _DEVICE_ID,
        "cartItems": mcp_items,
    })


def _parse_cart_items(text):
    """Parse view_cart text into list of {name, price, qty, pvid, spid}."""
    items = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _CART_ITEM_RE.match(line.strip())
        if m:
            item = {
                "name": m.group(1).strip(),
                "price": float(m.group(2)),
                "qty": int(m.group(3)),
                "pvid": "",
                "spid": "",
            }
            if i + 1 < len(lines):
                id_m = _CART_ID_RE.search(lines[i + 1])
                if id_m:
                    item["pvid"] = id_m.group(1)
                    item["spid"] = id_m.group(2)
            items.append(item)
    return items


def update_cart_items(access_token, items, address_id=None):
    """
    Replace the Zepto cart with the given items.
    items: [{pvid, spid, qty}] — items with qty <= 0 are excluded (effectively removed).
    Raises ValueError if all items are removed — Zepto MCP rejects cartItems:[].
    Use the Zepto app to clear the cart entirely.
    """
    session_id = _setup_for_cart(access_token, address_id=address_id)
    mcp_items = [
        {
            "productVariantId": i["pvid"],
            "storeProductId": i["spid"],
            "quantity": int(i["qty"]),
        }
        for i in items
        if i.get("pvid") and i.get("spid") and int(i.get("qty", 0)) > 0
    ]
    if not mcp_items:
        raise ValueError("cannot_clear_cart")
    return _mcp_tool(access_token, session_id, "update_cart", {
        "deviceId": _DEVICE_ID,
        "cartItems": mcp_items,
    })


def get_cart(access_token, address_id=None):
    """
    Fetch current Zepto cart via view_cart MCP tool.
    Returns {items: [{name, price, qty, pvid, spid}], total: float, count: int}.
    """
    session_id = _setup_for_cart(access_token, address_id=address_id)
    text = _mcp_tool(access_token, session_id, "view_cart", {})
    items = _parse_cart_items(text)
    total = sum(item["price"] * item["qty"] for item in items)
    return {"items": items, "total": round(total, 2), "count": len(items)}


def search_single_item(access_token, query, address_id=None):
    """
    Search Zepto for a single query string and return the product list.
    Used for the Swap flow — no confirmation token, no cart modification.
    Returns [{name, price, size, pvid, spid, previously_bought}].
    """
    session_id = _mcp_initialize(access_token)
    addr_text = _mcp_tool(access_token, session_id, "list_saved_addresses", {})
    if not address_id:
        address_id = _find_home_address_id(addr_text)
    if address_id:
        _mcp_tool(access_token, session_id, "select_saved_address", {"addressId": address_id})
    past_text = _mcp_tool(access_token, session_id, "get_past_order_items", {})
    past_orders = _parse_past_orders_full(past_text)

    search_text = _mcp_tool(access_token, session_id, "search_products", {"query": query})
    products = _parse_product_list(search_text)
    for p in products:
        p["previously_bought"] = any(
            _word_overlap_score(p["name"], po["name"]) >= 0.5
            for po in past_orders
        )
    return products


def swap_cart_item(access_token, old_pvid, new_pvid, new_spid, address_id=None):
    """
    Remove old_pvid from the current Zepto cart and add new_pvid/spid in its place.
    M-5: only update_cart is called, never order-placement tools.
    """
    session_id = _setup_for_cart(access_token, address_id=address_id)

    try:
        existing_text = _mcp_tool(access_token, session_id, "view_cart", {})
        existing = _parse_cart_items(existing_text)
    except Exception:
        existing = []

    merged = {
        item["pvid"]: {
            "productVariantId": item["pvid"],
            "storeProductId": item["spid"],
            "quantity": item["qty"],
        }
        for item in existing
        if item.get("pvid") and item["pvid"] != old_pvid  # drop old item
    }

    # Add new item (qty 1)
    merged[new_pvid] = {"productVariantId": new_pvid, "storeProductId": new_spid, "quantity": 1}

    return _mcp_tool(access_token, session_id, "update_cart", {
        "deviceId": _DEVICE_ID,
        "cartItems": list(merged.values()),
    })


def auto_add_shopping_items(access_token, tokens, address_id=None):
    """
    For each token, search Zepto → use Haiku to pick best product based on past orders →
    merge into existing cart → push via update_cart.

    Returns [{token, product_name, added, error}].
    M-5: only update_cart is called, never order-placement tools.
    """
    session_id = _mcp_initialize(access_token)

    addr_text = _mcp_tool(access_token, session_id, "list_saved_addresses", {})
    if not address_id:
        address_id = _find_home_address_id(addr_text)
    if address_id:
        _mcp_tool(access_token, session_id, "select_saved_address", {"addressId": address_id})

    past_text = _mcp_tool(access_token, session_id, "get_past_order_items", {})
    past_orders = _parse_past_orders_full(past_text)

    try:
        existing_text = _mcp_tool(access_token, session_id, "view_cart", {})
        existing = _parse_cart_items(existing_text)
    except Exception:
        existing = []

    merged = {
        item["pvid"]: {
            "productVariantId": item["pvid"],
            "storeProductId": item["spid"],
            "quantity": item["qty"],
        }
        for item in existing
        if item.get("pvid")
    }

    # Build a name lookup for existing cart items (for duplicate detection)
    existing_name_map = {item["pvid"]: item["name"] for item in existing if item.get("pvid")}

    results = []
    for token in tokens:
        try:
            # Duplicate guard: if cart already has a product that closely matches this
            # token, increment its qty instead of searching and possibly adding a
            # different brand — prevents accumulation from repeated auto-adds.
            similar_pvid = None
            similar_name = None
            for pvid, name in existing_name_map.items():
                if _word_overlap_score(name, token) >= 0.6 or _word_overlap_score(token, name) >= 0.6:
                    similar_pvid = pvid
                    similar_name = name
                    break

            if similar_pvid and similar_pvid in merged:
                merged[similar_pvid]["quantity"] += 1
                results.append({
                    "token": token,
                    "product_name": similar_name,
                    "pvid": similar_pvid,
                    "spid": merged[similar_pvid].get("storeProductId", ""),
                    "added": True,
                    "error": None,
                })
                continue

            search_text = _mcp_tool(access_token, session_id, "search_products", {"query": token})
            products = _parse_product_list(search_text)
            for p in products:
                # Word-overlap fuzzy match — tolerates minor name variations between
                # search_products and get_past_order_items text
                p["previously_bought"] = any(
                    _word_overlap_score(p["name"], po["name"]) >= 0.5
                    for po in past_orders
                )

            if not products:
                results.append({"token": token, "product_name": None, "added": False,
                                 "error": "No products found on Zepto"})
                continue

            best = _llm_select_product(products, past_orders)
            if not best or not best.get("pvid") or not best.get("spid"):
                results.append({"token": token, "product_name": None, "added": False,
                                 "error": "Product selection failed"})
                continue

            pvid, spid = best["pvid"], best["spid"]
            if pvid in merged:
                merged[pvid]["quantity"] += 1
            else:
                merged[pvid] = {"productVariantId": pvid, "storeProductId": spid, "quantity": 1}

            # Register new product in name map for subsequent tokens in same run
            existing_name_map[pvid] = best["name"]

            results.append({
                "token": token,
                "product_name": best["name"],
                "pvid": pvid,
                "spid": spid,
                "added": True,
                "error": None,
            })
        except Exception as exc:
            results.append({"token": token, "product_name": None, "added": False,
                             "error": str(exc)[:100]})

    if any(r["added"] for r in results):
        _mcp_tool(access_token, session_id, "update_cart", {
            "deviceId": _DEVICE_ID,
            "cartItems": list(merged.values()),
        })

    return results
