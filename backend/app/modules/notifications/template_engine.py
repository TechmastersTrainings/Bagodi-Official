import re
from typing import Any

SENSITIVE_KEYS = {"password", "token", "secret", "cvv", "card_number", "access_token", "refresh_token"}

DEFAULT_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "auth_otp": {
        "sms": {
            "body": "Your Bagodi verification code is {{ otp }}. Valid for 5 minutes. Never share this code.",
        },
        "whatsapp": {
            "body": "Your Bagodi verification code is {{ otp }}. Valid for 5 minutes. Never share this code with anyone.",
        },
    },
    "order_confirmed": {
        "sms": {
            "body": "Hello {{ customer_name }}, your order #{{ order_number }} for Rs.{{ total_amount }} has been confirmed. Bagodi Bidar.",
        },
        "whatsapp": {
            "body": "Hello {{ customer_name }}, your order #{{ order_number }} for Rs.{{ total_amount }} has been confirmed. Thank you for choosing Bagodi!",
        },
        "email": {
            "subject": "Order Confirmed - #{{ order_number }}",
            "body": "<h2>Order Confirmed</h2><p>Hello {{ customer_name }}, your order #{{ order_number }} for Rs.{{ total_amount }} has been successfully placed.</p>",
        },
    },
    "payment_captured": {
        "sms": {
            "body": "Payment of Rs.{{ amount }} for order #{{ order_number }} was successfully captured. Bagodi.",
        },
        "whatsapp": {
            "body": "Payment of Rs.{{ amount }} for order #{{ order_number }} has been received successfully. Bagodi Retail.",
        },
        "email": {
            "subject": "Payment Receipt for Order #{{ order_number }}",
            "body": "<h2>Payment Received</h2><p>We have successfully received payment of Rs.{{ amount }} for order #{{ order_number }}.</p>",
        },
    },
    "payment_failed": {
        "sms": {
            "body": "Payment for order #{{ order_number }} could not be completed. Please visit your account to retry payment. Bagodi.",
        },
        "whatsapp": {
            "body": "Payment for order #{{ order_number }} was unsuccessful. Please retry payment to avoid order cancellation.",
        },
    },
    "order_dispatched": {
        "sms": {
            "body": "Great news! Order #{{ order_number }} has been dispatched and is on its way to you. Bagodi.",
        },
        "whatsapp": {
            "body": "Your order #{{ order_number }} is out for delivery! Our delivery executive will reach your address shortly.",
        },
    },
    "order_delivered": {
        "sms": {
            "body": "Order #{{ order_number }} has been delivered. Thank you for shopping with Bagodi!",
        },
        "whatsapp": {
            "body": "Your order #{{ order_number }} has been delivered! We hope you love your purchase. Bagodi Retail.",
        },
        "email": {
            "subject": "Order Delivered - #{{ order_number }}",
            "body": "<h2>Order Delivered</h2><p>Your package for order #{{ order_number }} has been handed over.</p>",
        },
    },
    "order_cancelled": {
        "sms": {
            "body": "Order #{{ order_number }} has been cancelled. If payment was made, your refund is being processed. Bagodi.",
        },
        "whatsapp": {
            "body": "Order #{{ order_number }} has been cancelled. Any payments made will be refunded to your original source account.",
        },
        "email": {
            "subject": "Order Cancelled - #{{ order_number }}",
            "body": "<h2>Order Cancelled</h2><p>Your order #{{ order_number }} has been cancelled.</p>",
        },
    },
    "refund_succeeded": {
        "sms": {
            "body": "Refund of Rs.{{ amount }} for order #{{ order_number }} has been processed (Ref: {{ refund_reference }}). Bagodi.",
        },
        "whatsapp": {
            "body": "Refund of Rs.{{ amount }} for order #{{ order_number }} has been credited. Reference: {{ refund_reference }}. Bagodi Retail.",
        },
        "email": {
            "subject": "Refund Processed - #{{ order_number }}",
            "body": "<h2>Refund Processed</h2><p>A refund of Rs.{{ amount }} for order #{{ order_number }} has been processed successfully. Reference: {{ refund_reference }}.</p>",
        },
    },
    "cod_collected": {
        "sms": {
            "body": "Cash payment of Rs.{{ amount }} for order #{{ order_number }} collected by {{ collected_by }}. Bagodi.",
        },
        "whatsapp": {
            "body": "Cash payment of Rs.{{ amount }} for order #{{ order_number }} has been collected by delivery executive {{ collected_by }}.",
        },
    },
}


def sanitize_context(context: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive keys from template context to prevent data leaks."""
    safe: dict[str, Any] = {}
    for k, v in context.items():
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            safe[k] = "[REDACTED]"
        else:
            safe[k] = v
    return safe


def render_template_string(template_str: str, context: dict[str, Any]) -> str:
    """Interpolate {{ variable }} placeholders from sanitized context."""
    safe_context = sanitize_context(context)

    def replacer(match: re.Match) -> str:
        var_name = match.group(1).strip()
        val = safe_context.get(var_name)
        return str(val) if val is not None else ""

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replacer, template_str)
