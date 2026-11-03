from google.adk.agents import Agent
from ..config import settings
from .tools import (search_products, get_product, check_promotion, list_my_promotions,
                    get_order_status, list_my_orders)

MODEL = settings.GEMINI_MODEL

product_agent = Agent(
    name="product_agent", model=MODEL,
    description="Answers questions about products: search, specs, price, stock, comparisons.",
    instruction=("Use search_products / get_product. Never invent products or prices. "
                 "Show name, price, rating, key specs and stock status. Use a short table for comparisons. "
                 "If nothing matches, say so and suggest a broader search."),
    tools=[search_products, get_product],
)

promotion_agent = Agent(
    name="promotion_agent", model=MODEL,
    description="Checks promo codes and the user's eligibility; lists available promotions.",
    instruction=("Use check_promotion for a specific code and list_my_promotions for general questions. "
                 "State clearly: eligible or not, and every reason when not eligible. "
                 "Explain the discount, minimum order and expiry date. Never guess eligibility."),
    tools=[check_promotion, list_my_promotions],
)

order_agent = Agent(
    name="order_agent", model=MODEL,
    description="Reports order status, delivery estimate, tracking and totals.",
    instruction=("Use get_order_status for a given order ID and list_my_orders if no ID is given. "
                 "Report status, items, total, discount, carrier, tracking number and estimated delivery. "
                 "If an order is not found, say so; do not speculate."),
    tools=[get_order_status, list_my_orders],
)

root_agent = Agent(
    name="store_assistant", model=MODEL,
    description="Customer assistant for an electronics store.",
    instruction=("You are a friendly electronics store assistant. Route: product questions to product_agent, "
                 "promotions/codes/discounts to promotion_agent, orders/delivery/tracking to order_agent. "
                 "Answer greetings yourself. Keep answers short and clear."),
    sub_agents=[product_agent, promotion_agent, order_agent],
)
