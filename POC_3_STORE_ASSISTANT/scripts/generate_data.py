"""Regenerates data/*.json with dates relative to today (so promos are valid/expired as intended).
Run from POC_3_STORE_ASSISTANT: python scripts/generate_data.py
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)
now = datetime.now(timezone.utc).replace(microsecond=0)
d = lambda days: (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---- products ----
cols = ("id", "name", "brand", "category", "price", "rating", "stock_qty", "specs", "description")
rows = [
 ("E001","SonicPro NC700 Wireless Headphones","SonicPro","Headphones",179.0,4.6,25,"Active noise cancelling, 40h battery, Bluetooth 5.3, USB-C fast charge","Over-ear headphones with strong noise cancelling, ideal for travel and office."),
 ("E002","SonicPro Buds Air","SonicPro","Headphones",89.0,4.3,60,"In-ear, ANC, 8h battery, IPX4, wireless charging case","Compact true wireless earbuds for commuting and workouts."),
 ("E003","AudioMax Studio Wired Headphones","AudioMax","Headphones",129.0,4.7,15,"Wired, 50mm drivers, 3.5mm, detachable cable","Reference-quality closed-back headphones for music production."),
 ("E004","NovaBook Air 14 Laptop","NovaTech","Laptops",999.0,4.5,12,"14-inch OLED, 16GB RAM, 512GB SSD, 12h battery, 1.2kg","Ultra-light laptop for professionals who travel."),
 ("E005","NovaBook Pro 16 Laptop","NovaTech","Laptops",1799.0,4.8,0,"16-inch mini-LED, 32GB RAM, 1TB SSD, dedicated GPU","High-performance laptop for video editing and 3D work."),
 ("E006","ByteLite Student Laptop 15","ByteLite","Laptops",549.0,4.1,40,"15.6-inch FHD, 8GB RAM, 256GB SSD, 9h battery","Affordable everyday laptop for students and home use."),
 ("E007","Pixora X5 Smartphone","Pixora","Smartphones",699.0,4.6,30,"6.5-inch AMOLED 120Hz, 128GB, 50MP camera, 5000mAh, 5G","Flagship-class phone with excellent camera and long battery life."),
 ("E008","Pixora Lite 5G","Pixora","Smartphones",299.0,4.2,80,"6.4-inch LCD 90Hz, 64GB, 48MP camera, 4500mAh, 5G","Budget 5G phone with solid performance."),
 ("E009","ChronoFit Active Smartwatch","ChronoFit","Wearables",199.0,4.4,35,"1.4-inch AMOLED, GPS, heart-rate, 7-day battery, 5ATM water resistant","Fitness smartwatch with GPS and sleep tracking."),
 ("E010","VistaView 55 4K Smart TV","VistaView","TVs",649.0,4.5,10,"55-inch 4K QLED, 120Hz, HDMI 2.1, Dolby Vision, Google TV","Bright 4K TV, great for gaming and movies."),
 ("E011","BoomBox Mini Bluetooth Speaker","AudioMax","Speakers",59.0,4.4,70,"Portable, IP67 waterproof, 12h battery, Bluetooth 5.2","Rugged pocket speaker for outdoors and the pool."),
 ("E012","PowerCore 20000 Power Bank","VoltEdge","Accessories",45.0,4.7,100,"20000mAh, 65W USB-C PD, charges laptops, 2 ports","High-capacity power bank that can charge a laptop."),
]
P = {r[0]: dict(zip(cols, r)) for r in rows}
for p in P.values():
    p["in_stock"] = p["stock_qty"] > 0

# ---- users ----
users = [
 dict(user_id="U001", name="Aisha Khan", email="aisha@example.com", tier="gold", signup_date=d(-700), total_orders=3, lifetime_spend=1296.4, promo_usage={"WELCOME10": 1, "AUDIO20": 1}),
 dict(user_id="U002", name="Omar Ali", email="omar@example.com", tier="silver", signup_date=d(-300), total_orders=2, lifetime_spend=943.0, promo_usage={}),
 dict(user_id="U003", name="Lina Haddad", email="lina@example.com", tier="platinum", signup_date=d(-900), total_orders=2, lifetime_spend=649.0, promo_usage={}),
 dict(user_id="U004", name="Sam Carter", email="sam@example.com", tier="standard", signup_date=d(-5), total_orders=0, lifetime_spend=0.0, promo_usage={}),
]

# ---- promotions ----
def promo(code, desc, dtype, value, min_order, tiers, cats, new_only, max_uses, start, end, active=True):
    return dict(code=code, description=desc, discount_type=dtype, discount_value=value,
                min_order_value=min_order, eligible_tiers=tiers, eligible_categories=cats,
                new_users_only=new_only, max_uses_per_user=max_uses,
                valid_from=d(start), valid_to=d(end), active=active)

promotions = [
 promo("WELCOME10", "10% off first order", "PERCENT", 10, 50, [], [], True, 1, -30, 60),
 promo("GOLD15", "15% off for Gold and Platinum members", "PERCENT", 15, 200, ["gold", "platinum"], [], False, 5, -10, 30),
 promo("AUDIO20", "20% off headphones and speakers", "PERCENT", 20, 0, [], ["Headphones", "Speakers"], False, 1, -5, 14),
 promo("FLAT50", "$50 off orders above $500", "FLAT", 50, 500, ["silver", "gold", "platinum"], [], False, 2, -5, 20),
 promo("PLAT30", "30% off laptops for Platinum members", "PERCENT", 30, 0, ["platinum"], ["Laptops"], False, 1, -5, 45),
 promo("BLACKFRI25", "25% off sitewide (ended)", "PERCENT", 25, 0, [], [], False, 1, -40, -5),
]

# ---- orders ----
def order(oid, uid, status, placed_days_ago, eta_days, items, promo_code=None, discount=0.0,
          carrier=None, tracking=None, note=None):
    lines = [dict(product_id=p, name=P[p]["name"], qty=q, unit_price=P[p]["price"]) for p, q in items]
    subtotal = round(sum(l["qty"] * l["unit_price"] for l in lines), 2)
    return dict(order_id=oid, user_id=uid, status=status, order_date=d(-placed_days_ago),
                estimated_delivery=d(eta_days) if eta_days is not None else None, items=lines,
                subtotal=subtotal, promo_code=promo_code, discount=discount,
                total=round(subtotal - discount, 2), carrier=carrier,
                tracking_number=tracking, status_note=note)

orders = [
 order("O1001","U001","DELIVERED",20,-15,[("E001",1)],carrier="DHL",tracking="DHL100001",note="Delivered to front desk"),
 order("O1002","U001","SHIPPED",3,2,[("E004",1)],carrier="DHL",tracking="DHL100002",note="In transit"),
 order("O1007","U001","PROCESSING",1,6,[("E002",1),("E011",1)],promo_code="AUDIO20",discount=29.6,note="Being packed"),
 order("O1003","U002","PROCESSING",1,5,[("E007",1),("E012",1)],note="Payment confirmed"),
 order("O1004","U002","OUT_FOR_DELIVERY",4,0,[("E009",1)],carrier="FedEx",tracking="FDX100004",note="Out for delivery today"),
 order("O1005","U003","CANCELLED",10,None,[("E005",1)],note="Cancelled: item out of stock. Refund issued."),
 order("O1006","U003","DELIVERED",30,-24,[("E010",1)],carrier="UPS",tracking="UPS100006",note="Delivered"),
]

for name, docs in [("products", list(P.values())), ("users", users), ("promotions", promotions), ("orders", orders)]:
    (OUT / f"{name}.json").write_text(json.dumps(docs, indent=2))
    print(f"data/{name}.json: {len(docs)} docs")
