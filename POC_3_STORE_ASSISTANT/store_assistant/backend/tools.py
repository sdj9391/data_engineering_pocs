from datetime import datetime, timezone
from google.adk.tools import ToolContext
from google.cloud import firestore

from ..config import settings

db = firestore.Client(
    project=settings.GOOGLE_CLOUD_PROJECT,
    database=settings.FIRESTORE_DB,
)


def _uid(ctx: ToolContext) -> str:
    # user_id is set in session state by the backend; the env fallback is for local `adk web` only
    return ctx.state.get("user_id") or settings.DEFAULT_USER_ID


def _clean(d: dict) -> dict:
    return {k: (v.strftime("%Y-%m-%d") if isinstance(v, datetime) else v) for k, v in d.items()}


# ---------- product tools ----------
def search_products(query: str = "", category: str = "", max_price: float = 0) -> dict:
    """Searches the product catalog.

    Args:
        query: Keywords such as "noise cancelling headphones". Empty returns top-rated items.
        category: Optional exact category: Headphones, Laptops, Smartphones, Wearables, TVs, Speakers, Accessories.
        max_price: Optional maximum price in USD. 0 means no limit.
    """
    terms = query.lower().split()
    scored = []
    for doc in db.collection("products").stream():
        p = doc.to_dict()
        if category and p["category"].lower() != category.lower():
            continue
        if max_price and p["price"] > max_price:
            continue
        text = " ".join(str(p[k]) for k in ("name", "brand", "category", "specs", "description")).lower()
        score = sum(t in text for t in terms)
        if terms and score == 0:
            continue
        scored.append((score, p["rating"], p))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return {"status": "success", "products": [_clean(s[2]) for s in scored[:5]]}


def get_product(product_id: str) -> dict:
    """Gets full details of one product by ID, e.g. "E001"."""
    doc = db.collection("products").document(product_id.upper()).get()
    return {"status": "success", "product": _clean(doc.to_dict())} if doc.exists else {"status": "not_found"}


# ---------- promotion tools ----------
def _evaluate(p: dict, u: dict, cart_value: float, category: str) -> list:
    now = datetime.now(timezone.utc)
    why = []
    if not p["active"]:
        why.append("promotion is inactive")
    if now < p["valid_from"]:
        why.append(f"starts on {p['valid_from']:%Y-%m-%d}")
    if now > p["valid_to"]:
        why.append(f"expired on {p['valid_to']:%Y-%m-%d}")
    if p["eligible_tiers"] and u["tier"] not in p["eligible_tiers"]:
        why.append(f"requires tier {'/'.join(p['eligible_tiers'])}; your tier is {u['tier']}")
    if p["new_users_only"] and u["total_orders"] > 0:
        why.append("valid for first-time customers only")
    if u["promo_usage"].get(p["code"], 0) >= p["max_uses_per_user"]:
        why.append(f"already used the maximum {p['max_uses_per_user']} time(s)")
    if p["eligible_categories"] and category and category not in p["eligible_categories"]:
        why.append(f"only applies to {', '.join(p['eligible_categories'])}")
    if cart_value and cart_value < p["min_order_value"]:
        why.append(f"minimum order value is ${p['min_order_value']}; cart is ${cart_value}")
    return why


def check_promotion(promo_code: str, tool_context: ToolContext, cart_value: float = 0, category: str = "") -> dict:
    """Checks whether the current user can use a promotion code.

    Args:
        promo_code: The code, e.g. "GOLD15".
        cart_value: Optional cart total in USD to test the minimum order rule. 0 if unknown.
        category: Optional product category in the cart.
    """
    pdoc = db.collection("promotions").document(promo_code.upper()).get()
    if not pdoc.exists:
        return {"status": "not_found", "message": f"No promotion with code {promo_code}"}
    p = pdoc.to_dict()
    u = db.collection("users").document(_uid(tool_context)).get().to_dict()
    reasons = _evaluate(p, u, cart_value, category)
    return {"status": "success", "eligible": not reasons, "reasons_not_eligible": reasons,
            "promotion": _clean({k: p[k] for k in ("code", "description", "discount_type", "discount_value",
                                                   "min_order_value", "eligible_tiers", "eligible_categories",
                                                   "valid_from", "valid_to")}),
            "user_tier": u["tier"]}


def list_my_promotions(tool_context: ToolContext) -> dict:
    """Lists currently running promotions and whether the current user is eligible for each."""
    u = db.collection("users").document(_uid(tool_context)).get().to_dict()
    now = datetime.now(timezone.utc)
    out = []
    for doc in db.collection("promotions").stream():
        p = doc.to_dict()
        if not p["active"] or not (p["valid_from"] <= now <= p["valid_to"]):
            continue
        why = _evaluate(p, u, 0, "")
        out.append({"code": p["code"], "description": p["description"], "eligible": not why,
                    "reasons_not_eligible": why, "valid_to": f"{p['valid_to']:%Y-%m-%d}"})
    return {"status": "success", "promotions": out}


# ---------- order tools ----------
def get_order_status(order_id: str, tool_context: ToolContext) -> dict:
    """Gets status and details of one of the current user's orders, e.g. "O1002"."""
    doc = db.collection("orders").document(order_id.upper()).get()
    # Same response for "missing" and "someone else's" so other users' orders are not revealed
    if not doc.exists or doc.to_dict()["user_id"] != _uid(tool_context):
        return {"status": "not_found", "message": f"No order {order_id} found for your account"}
    return {"status": "success", "order": _clean(doc.to_dict())}


def list_my_orders(tool_context: ToolContext) -> dict:
    """Lists the current user's recent orders, newest first."""
    docs = db.collection("orders").where("user_id", "==", _uid(tool_context)).stream()
    orders = sorted((d.to_dict() for d in docs), key=lambda o: o["order_date"], reverse=True)
    return {"status": "success", "orders": [_clean(o) for o in orders[:10]]}
