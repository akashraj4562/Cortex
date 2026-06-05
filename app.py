import os
import secrets
import hashlib
import base64
import threading
import time
from urllib.parse import urlencode

import requests as http_requests
from flask import Flask, request, jsonify, render_template, send_file

import db
import scraper
import classifier
import splitter
import type_manager
import image_processor
from zepto_client import encrypt_token, decrypt_token, search_all_items, add_items_to_cart, list_all_addresses, get_cart, update_cart_items, auto_add_shopping_items, search_single_item, swap_cart_item
from config import (
    PORT, REMINDER_POLL_INTERVAL,
    ZEPTO_OAUTH_AUTH_URL, ZEPTO_OAUTH_TOKEN_URL,
    ZEPTO_CLIENT_ID, ZEPTO_OAUTH_REDIRECT_URI,
)

app = Flask(__name__)
db.init_db()

# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def _process_one(raw_item):
    """Classify and store a single item. Returns the saved card dict."""
    url, topic_hint, explicit_type = classifier.parse_input(raw_item)
    scraped_text = scraper.scrape(url) if url else None

    result = classifier.classify(
        raw_input=raw_item,
        scraped_text=scraped_text,
        source_url=url,
        topic_hint=topic_hint,
        explicit_type=explicit_type,
    )

    routing = result.get("routing", "assign")

    # If Corty created a new type, register it in DB before inserting the capture
    if routing == "new_type":
        ntype = result.get("suggested_new_type") or {}
        if ntype.get("key"):
            db.create_type(
                key=ntype["key"],
                label=ntype.get("label", ntype["key"].replace("_", " ").title()),
                icon=ntype.get("icon", "?"),
                color="#6248d8",
                description=f"Corty-created: {ntype.get('label', '')}",
            )

    # For shopping_list text captures, run Haiku extraction to get structured items
    if result["type"] == "shopping_list":
        extracted = classifier.extract_shopping_items(raw_item)
        if extracted:
            result.setdefault("metadata", {})["items"] = extracted

    capture_id = db.insert_capture(
        raw_input=raw_item,
        content_type=result["type"],
        confidence=result["confidence"],
        rationale=result.get("rationale", ""),
        metadata=result.get("metadata", {}),
        tags=result.get("tags", []),
    )

    # Trigger async clustering when a capture lands in Unknown
    if routing == "unknown" and type_manager.should_cluster():
        threading.Thread(target=type_manager.cluster_unknown, daemon=True).start()

    return db.get_capture(capture_id)


@app.route("/api/capture/image", methods=["POST"])
def capture_image():
    body = request.get_json(silent=True) or {}
    b64 = (body.get("image") or "").strip()
    media_type = (body.get("media_type") or "image/jpeg").strip()
    hint = (body.get("hint") or "").strip()

    if not b64:
        return jsonify({"error": "image field is required"}), 400

    # Process: orient, resize, save
    try:
        proc = image_processor.process_image(b64, media_type)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    image_path = proc["image_path"]
    b64_jpeg = proc["base64_jpeg"]

    # Classify via vision
    try:
        result = classifier.classify_image(b64_jpeg, "image/jpeg", hint=hint)
    except Exception as e:
        return jsonify({"error": f"Classification failed: {str(e)[:120]}"}), 500

    routing = result.get("routing", "assign")

    if routing == "new_type":
        ntype = result.get("suggested_new_type") or {}
        if ntype.get("key"):
            db.create_type(
                key=ntype["key"],
                label=ntype.get("label", ntype["key"].replace("_", " ").title()),
                icon=ntype.get("icon", "?"),
                color="#6248d8",
                description=f"Corty-created: {ntype.get('label', '')}",
            )

    # Auto-reminder check
    meta = result.get("metadata", {})
    structured = meta.get("structured_data") or {}
    due_date = structured.get("due_date")
    confidence = result.get("confidence", 0)

    linked_reminder_id = None
    if due_date:
        if confidence >= 0.70:
            reminder_meta = {
                "task": f"{meta.get('description', 'Image capture')} — extracted from image",
                "due_date": due_date,
                "priority": "medium",
                "source_capture_id": None,  # filled after image capture inserted
            }
            linked_reminder_id = db.insert_capture(
                raw_input=f"[auto-reminder] {meta.get('description', '')}",
                content_type="reminder",
                confidence=confidence,
                rationale="Auto-extracted from image capture",
                metadata=reminder_meta,
                tags=[],
                input_type="text",
            )
        else:
            meta["_extract_reminder"] = True

    meta["image_path"] = image_path

    capture_id = db.insert_capture(
        raw_input=hint or "[image capture]",
        content_type=result["type"],
        confidence=confidence,
        rationale=result.get("rationale", ""),
        metadata=meta,
        tags=result.get("tags", []),
        image_path=image_path,
        input_type="image",
    )

    # Back-fill source_capture_id on the reminder and linked_reminder_id on the image capture
    if linked_reminder_id:
        with db.get_conn() as conn:
            import json as _json
            row = conn.execute("SELECT metadata FROM captures WHERE id=?", (linked_reminder_id,)).fetchone()
            if row:
                rm = _json.loads(row["metadata"])
                rm["source_capture_id"] = capture_id
                conn.execute("UPDATE captures SET metadata=? WHERE id=?",
                             (_json.dumps(rm), linked_reminder_id))
            img_row = conn.execute("SELECT metadata FROM captures WHERE id=?", (capture_id,)).fetchone()
            if img_row:
                im = _json.loads(img_row["metadata"])
                im["linked_reminder_id"] = linked_reminder_id
                conn.execute("UPDATE captures SET metadata=? WHERE id=?",
                             (_json.dumps(im), capture_id))

    if routing == "unknown" and type_manager.should_cluster():
        threading.Thread(target=type_manager.cluster_unknown, daemon=True).start()

    return jsonify(db.get_capture(capture_id)), 201


@app.route("/api/capture", methods=["POST"])
def capture():
    body = request.get_json(silent=True) or {}
    raw = (body.get("text") or "").strip()

    if not raw:
        return jsonify({"error": "Empty input"}), 400

    items = splitter.split_items(raw)

    if len(items) == 1:
        card = _process_one(items[0])
        return jsonify(card), 201

    # Multi-item: process each and return array
    cards = [_process_one(item) for item in items]
    return jsonify({"cards": cards, "count": len(cards)}), 201


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

@app.route("/api/types")
def get_types():
    types = db.get_all_types()
    # Return as ordered list: seeds first, then dynamic; exclude system/legacy types from UI
    _ui_excluded = {"unknown", "unclassified", "blog_post", "job_post"}
    result = [
        {"key": k, "label": v["label"], "icon": v["icon"], "color": v["color"], "is_seed": v["is_seed"]}
        for k, v in types.items()
        if k not in _ui_excluded
    ]
    result.sort(key=lambda t: (0 if t["is_seed"] else 1, t["key"]))
    return jsonify(result)


@app.route("/api/unknown/resolve", methods=["POST"])
def resolve_unknown():
    body = request.get_json(silent=True) or {}
    capture_id = body.get("id")
    new_type = (body.get("type") or "").strip()
    if not capture_id or not new_type:
        return jsonify({"error": "id and type are required"}), 400
    db.resolve_unknown(capture_id, new_type)
    card = db.get_capture(capture_id)
    return jsonify({"ok": True, "card": card})


@app.route("/api/feed")
def feed():
    ct = request.args.get("type") or None
    grouped_types = {"learning", "food_for_thought", "build_better", "interview_exp"}

    if ct in grouped_types:
        groups = db.get_captures_grouped_by_topic(content_type=ct)
        badge = db.get_due_today_count()
        return jsonify({"groups": groups, "reminder_badge": badge, "grouped": True})

    cards = db.get_captures(content_type=ct)
    badge = db.get_due_today_count()
    return jsonify({"cards": cards, "reminder_badge": badge, "grouped": False})


@app.route("/api/image/<int:capture_id>")
def serve_image(capture_id):
    card = db.get_capture(capture_id)
    if not card:
        return jsonify({"error": "Not found"}), 404
    image_path = card.get("metadata", {}).get("image_path")
    if not image_path or not os.path.exists(image_path):
        return jsonify({"error": "Image not found"}), 404
    return send_file(image_path, mimetype="image/jpeg")


@app.route("/api/counts")
def counts():
    return jsonify(db.get_tab_counts())


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@app.route("/api/capture/<int:capture_id>/archive", methods=["POST"])
def archive(capture_id):
    db.archive_capture(capture_id)
    return jsonify({"ok": True})


@app.route("/api/capture/<int:capture_id>/complete", methods=["POST"])
def complete(capture_id):
    db.complete_capture(capture_id)
    badge = db.get_due_today_count()
    return jsonify({"ok": True, "reminder_badge": badge})


@app.route("/api/badge")
def badge():
    return jsonify({"reminder_badge": db.get_due_today_count()})


# ---------------------------------------------------------------------------
# Zepto integration
# ---------------------------------------------------------------------------

# PKCE state store — persisted to DB so server restarts don't break in-flight OAuth flows


@app.route("/api/zepto/status")
def zepto_status():
    encrypted = db.get_zepto_token()
    return jsonify({"connected": encrypted is not None})


@app.route("/api/zepto/init")
def zepto_init():
    if not ZEPTO_CLIENT_ID:
        return jsonify({"error": "ZEPTO_CLIENT_ID not configured"}), 500

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(32)
    db.store_oauth_state(state, code_verifier)

    params = {
        "response_type": "code",
        "client_id": ZEPTO_CLIENT_ID,
        "redirect_uri": ZEPTO_OAUTH_REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "resource": "https://mcp.zepto.co.in",  # RFC 8707 — audience for MCP server
    }
    auth_url = f"{ZEPTO_OAUTH_AUTH_URL}?{urlencode(params)}"
    return jsonify({"auth_url": auth_url})


@app.route("/api/zepto/callback")
def zepto_callback():
    error = request.args.get("error", "").strip()
    if error:
        error_desc = request.args.get("error_description", error)[:200]
        return render_template("index.html", zepto_error=error_desc)

    code = request.args.get("code", "").strip()
    state = request.args.get("state", "").strip()

    if not code or not state:
        return jsonify({"error": "Missing code or state parameter"}), 400

    code_verifier = db.consume_oauth_state(state)
    if not code_verifier:
        return jsonify({"error": "Invalid or expired OAuth state"}), 400

    try:
        token_resp = http_requests.post(
            ZEPTO_OAUTH_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": ZEPTO_OAUTH_REDIRECT_URI,
                "client_id": ZEPTO_CLIENT_ID,
                "code_verifier": code_verifier,
                "resource": "https://mcp.zepto.co.in",  # RFC 8707 — bind token to MCP server
            },
            timeout=10,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
    except Exception:
        return jsonify({"error": "Token exchange with Zepto failed"}), 502

    access_token = token_data.get("access_token")
    if not access_token:
        return jsonify({"error": "No access_token in Zepto response"}), 502

    encrypted = encrypt_token(access_token)
    db.store_zepto_token(encrypted)
    db.log_event("zepto_connected", {})

    return render_template("index.html")


@app.route("/api/zepto/addresses")
def zepto_addresses():
    encrypted = db.get_zepto_token()
    if not encrypted:
        return jsonify({"error": "Zepto not connected", "code": "not_connected"}), 401
    try:
        access_token = decrypt_token(encrypted)
    except ValueError:
        return jsonify({"error": "Zepto token invalid — please reconnect"}), 401
    try:
        addresses = list_all_addresses(access_token)
    except Exception as e:
        return jsonify({"error": f"Failed to load addresses: {str(e)[:120]}"}), 502
    return jsonify({"addresses": addresses})


@app.route("/api/zepto/search", methods=["POST"])
def zepto_search():
    encrypted = db.get_zepto_token()
    if not encrypted:
        return jsonify({"error": "Zepto not connected", "code": "not_connected"}), 401

    body = request.get_json(silent=True) or {}
    capture_id = body.get("capture_id")
    address_id  = (body.get("address_id") or "").strip() or None
    if not capture_id:
        return jsonify({"error": "capture_id is required"}), 400

    card = db.get_capture(int(capture_id))
    if not card or card.get("type") != "shopping_list":
        return jsonify({"error": "Not a shopping_list capture"}), 400

    items = card.get("metadata", {}).get("items", [])
    if not items:
        return jsonify({"error": "No items found in shopping list"}), 400

    try:
        access_token = decrypt_token(encrypted)
    except ValueError:
        return jsonify({"error": "Zepto token invalid — please reconnect"}), 401

    item_names = [
        i.get("name", str(i)) if isinstance(i, dict) else str(i)
        for i in items
    ]

    try:
        results = search_all_items(access_token, item_names, address_id=address_id)
    except Exception as e:
        return jsonify({"error": f"Zepto search failed: {str(e)[:120]}"}), 502

    confirmation_items = []
    not_found = []
    for item_name, products in results.items():
        if products:
            # Previously bought products sort first
            products_sorted = sorted(products, key=lambda p: (0 if p.get("previously_bought") else 1))
            confirmation_items.append({
                "query": item_name,
                "selected_product": products_sorted[0],
                "alternatives": products_sorted[1:5],
                "quantity": 1,
            })
        else:
            not_found.append(item_name)

    confirmation_token = db.create_pending_cart_op(confirmation_items)
    db.log_event("zepto_search", {"capture_id": capture_id, "item_count": len(item_names)})

    return jsonify({
        "confirmation_items": confirmation_items,
        "confirmation_token": confirmation_token,
        "not_found": not_found,
    })


@app.route("/api/zepto/cart-add", methods=["POST"])
def zepto_cart_add():
    encrypted = db.get_zepto_token()
    if not encrypted:
        return jsonify({"error": "Zepto not connected", "code": "not_connected"}), 401

    body = request.get_json(silent=True) or {}
    confirmation_token = (body.get("confirmation_token") or "").strip()
    product_overrides  = body.get("products") or []
    address_id         = (body.get("address_id") or "").strip() or None

    if not confirmation_token:
        return jsonify({"error": "confirmation_token is required"}), 403

    items = db.consume_pending_cart_op(confirmation_token)
    if items is None:
        return jsonify({"error": "Invalid or expired confirmation_token"}), 403

    try:
        access_token = decrypt_token(encrypted)
    except ValueError:
        return jsonify({"error": "Zepto token invalid — please reconnect"}), 401

    # Index-keyed override map: {str(idx): {pvid, spid, quantity}}
    override_map = {str(p["idx"]): p for p in product_overrides if "idx" in p}

    cart_items = []
    failed = []
    item_queries = []

    for idx, item in enumerate(items):
        query = item.get("query", "")
        ov = override_map.get(str(idx))
        if ov:
            pvid = ov.get("pvid", "")
            spid = ov.get("spid", "")
            quantity = int(ov.get("quantity", 1))
        else:
            product = item.get("selected_product") or {}
            pvid = product.get("pvid", "")
            spid = product.get("spid", "")
            quantity = int(item.get("quantity") or 1)

        if not pvid or not spid:
            failed.append({"query": query, "reason": "no product selected"})
            continue

        cart_items.append({"pvid": pvid, "spid": spid, "quantity": quantity})
        item_queries.append(query)

    added = []
    if cart_items:
        try:
            add_items_to_cart(access_token, cart_items, address_id=address_id)
            added = [{"query": q} for q in item_queries]
        except Exception as e:
            failed.extend([{"query": q, "reason": str(e)[:120]} for q in item_queries])

    db.log_event("zepto_cart_add", {"added_count": len(added), "failed_count": len(failed)})

    return jsonify({"added": added, "failed": failed, "total": len(items)})


@app.route("/api/zepto/cart")
def zepto_view_cart():
    encrypted = db.get_zepto_token()
    if not encrypted:
        return jsonify({"error": "Zepto not connected", "code": "not_connected"}), 401
    try:
        access_token = decrypt_token(encrypted)
    except ValueError:
        return jsonify({"error": "Zepto token invalid — please reconnect"}), 401
    address_id = (request.args.get("address_id") or "").strip() or None
    try:
        result = get_cart(access_token, address_id=address_id)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch cart: {str(e)[:120]}"}), 502
    return jsonify(result)


@app.route("/api/zepto/cart/update", methods=["POST"])
def zepto_cart_update():
    encrypted = db.get_zepto_token()
    if not encrypted:
        return jsonify({"error": "Zepto not connected", "code": "not_connected"}), 401
    try:
        access_token = decrypt_token(encrypted)
    except ValueError:
        return jsonify({"error": "Zepto token invalid — please reconnect"}), 401
    body = request.get_json(silent=True) or {}
    items = body.get("items") or []
    address_id = (body.get("address_id") or "").strip() or None
    try:
        update_cart_items(access_token, items, address_id=address_id)
    except ValueError as e:
        if "cannot_clear_cart" in str(e):
            return jsonify({"error": "cannot_clear_cart"}), 422
        app.logger.error("zepto cart update ValueError: %s", e)
        return jsonify({"error": str(e)[:200]}), 400
    except Exception as e:
        app.logger.error("zepto cart update error: %s", e)
        return jsonify({"error": str(e)[:200]}), 502
    return jsonify({"ok": True})


@app.route("/api/zepto/auto-add", methods=["POST"])
def zepto_auto_add():
    encrypted = db.get_zepto_token()
    if not encrypted:
        return jsonify({"error": "Zepto not connected", "code": "not_connected"}), 401
    try:
        access_token = decrypt_token(encrypted)
    except ValueError:
        return jsonify({"error": "Zepto token invalid — please reconnect"}), 401

    body = request.get_json(silent=True) or {}
    tokens = [t.strip() for t in (body.get("tokens") or []) if str(t).strip()]
    capture_id = body.get("capture_id")
    address_id = (body.get("address_id") or "").strip() or None

    if not tokens:
        return jsonify({"error": "No tokens provided"}), 400

    try:
        results = auto_add_shopping_items(access_token, tokens, address_id=address_id)
    except Exception as e:
        return jsonify({"error": f"Auto-add failed: {str(e)[:120]}"}), 502

    added_count = sum(1 for r in results if r["added"])
    if capture_id and added_count > 0:
        db.archive_capture(int(capture_id))
        # Store what was added so the card can show per-item results + Swap buttons
        capture = db.get_capture(int(capture_id))
        if capture:
            meta = capture.get("metadata") or {}
            meta["auto_add_results"] = results
            db.update_capture_metadata(int(capture_id), meta)

    db.log_event("zepto_auto_add", {"token_count": len(tokens), "added": added_count})
    return jsonify({"results": results, "archived": capture_id is not None and added_count > 0})


@app.route("/api/zepto/search-simple", methods=["POST"])
def zepto_search_simple():
    """Search Zepto for a single query string. Used by the Swap flow."""
    encrypted = db.get_zepto_token()
    if not encrypted:
        return jsonify({"error": "Zepto not connected"}), 401
    try:
        access_token = decrypt_token(encrypted)
    except ValueError:
        return jsonify({"error": "Zepto token invalid"}), 401

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        products = search_single_item(access_token, query)
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)[:120]}"}), 502

    return jsonify({"products": products})


@app.route("/api/zepto/swap", methods=["POST"])
def zepto_swap():
    """Remove old cart item and add a replacement. Used by the Swap ↻ flow."""
    encrypted = db.get_zepto_token()
    if not encrypted:
        return jsonify({"error": "Zepto not connected"}), 401
    try:
        access_token = decrypt_token(encrypted)
    except ValueError:
        return jsonify({"error": "Zepto token invalid"}), 401

    body = request.get_json(silent=True) or {}
    old_pvid = (body.get("old_pvid") or "").strip()
    new_pvid = (body.get("new_pvid") or "").strip()
    new_spid = (body.get("new_spid") or "").strip()
    capture_id = body.get("capture_id")
    new_product_name = (body.get("new_product_name") or "").strip()
    token_query = (body.get("token_query") or "").strip()

    if not old_pvid or not new_pvid or not new_spid:
        return jsonify({"error": "Missing pvid/spid"}), 400

    try:
        swap_cart_item(access_token, old_pvid, new_pvid, new_spid)
    except Exception as e:
        return jsonify({"error": f"Swap failed: {str(e)[:120]}"}), 502

    # Update stored auto_add_results so the card reflects the new product
    if capture_id and new_product_name:
        try:
            capture = db.get_capture(int(capture_id))
            if capture:
                meta = capture.get("metadata") or {}
                results = meta.get("auto_add_results") or []
                for r in results:
                    if r.get("pvid") == old_pvid or r.get("token") == token_query:
                        r["product_name"] = new_product_name
                        r["pvid"] = new_pvid
                        r["spid"] = new_spid
                        break
                meta["auto_add_results"] = results
                db.update_capture_metadata(int(capture_id), meta)
        except Exception:
            pass

    db.log_event("zepto_swap", {"old_pvid": old_pvid[:8], "new_pvid": new_pvid[:8]})
    return jsonify({"success": True, "product_name": new_product_name})


@app.route("/api/feed/archived")
def feed_archived():
    ct = request.args.get("type") or None
    cards = db.get_archived_captures(content_type=ct)
    return jsonify({"cards": cards})


@app.route("/api/zepto/disconnect", methods=["POST"])
def zepto_disconnect():
    db.delete_zepto_token()
    db.log_event("zepto_disconnected", {})
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Reminder background thread
# ---------------------------------------------------------------------------

def _reminder_poll():
    while True:
        time.sleep(REMINDER_POLL_INTERVAL)
        # Badge count computed on-demand via /api/badge.
        # Thread exists for future push/alert logic.


threading.Thread(target=_reminder_poll, daemon=True).start()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "unknown"
    print(f"\n  CORTEX running at:")
    print(f"    Local:   http://localhost:{PORT}")
    print(f"    Network: http://{local_ip}:{PORT}  ← open this on your phone\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
