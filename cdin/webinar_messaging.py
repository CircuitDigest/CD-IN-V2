import os
from typing import Any, Dict

import requests


class WebinarMessagingError(Exception):
    pass


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise WebinarMessagingError(f"Missing environment variable: {name}")
    return value


def send_msg91_email(to_email: str, template_name: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    auth_key = _require_env("MSG91_EMAIL_AUTHKEY")
    domain = (os.environ.get("MSG91_EMAIL_DOMAIN") or "").strip() or "mail.circuitdigest.cloud"
    from_email = (os.environ.get("MSG91_EMAIL_FROM") or "").strip() or f"no-reply@{domain}"
    from_name = (os.environ.get("MSG91_EMAIL_FROM_NAME") or "").strip() or "CircuitDigest Webinar Team"
    to_name = str(variables.get("name") or "Participant")

    payload = {
        "recipients": [
            {
                "to": [{"email": to_email, "name": to_name}],
                "variables": variables,
            }
        ],
        "from": {"email": from_email, "name": from_name},
        "domain": domain,
        "template_id": template_name,
    }

    response = requests.post(
        "https://control.msg91.com/api/v5/email/send",
        json=payload,
        headers={"authkey": auth_key, "Content-Type": "application/json"},
        timeout=20,
    )
    if response.status_code >= 300:
        raise WebinarMessagingError(f"MSG91 email failed: {response.status_code} {response.text[:300]}")

    data = response.json() if response.content else {}
    return {"ok": True, "provider_message_id": str(data.get("request_id", ""))}


def send_msg91_whatsapp(phone_e164: str, template_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    auth_key = _require_env("MSG91_WHATSAPP_AUTHKEY")
    integrated_number = _require_env("MSG91_WHATSAPP_NUMBER")
    namespace = os.environ.get("MSG91_WHATSAPP_TEMPLATE_NAMESPACE", "").strip()

    # MSG91 supports multiple variable naming schemes depending on how the template
    # was created. We support both:
    # - legacy: body_1..body_4
    # - named:  body_var_1..body_var_N with parameter_name var_1..var_N
    if any(k.startswith("var_") for k in params.keys()):
        components: Dict[str, Any] = {}
        for i in range(1, 9):
            key = f"var_{i}"
            if key not in params:
                continue
            components[f"body_var_{i}"] = {
                "type": "text",
                "value": str(params.get(key, "")),
                "parameter_name": key,
            }
    else:
        components = {
            "body_1": {"type": "text", "value": str(params.get("body_1", ""))},
            "body_2": {"type": "text", "value": str(params.get("body_2", ""))},
            "body_3": {"type": "text", "value": str(params.get("body_3", ""))},
            "body_4": {"type": "text", "value": str(params.get("body_4", ""))},
        }

    payload = {
        "integrated_number": integrated_number,
        "content_type": "template",
        "payload": {
            "messaging_product": "whatsapp",
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en", "policy": "deterministic"},
                "to_and_components": [
                    {
                        "to": [phone_e164],
                        "components": components,
                    }
                ],
            },
        },
    }
    if namespace:
        payload["payload"]["template"]["namespace"] = namespace

    response = requests.post(
        "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/",
        json=payload,
        headers={"authkey": auth_key, "Content-Type": "application/json"},
        timeout=20,
    )
    if response.status_code >= 300:
        raise WebinarMessagingError(
            f"MSG91 WhatsApp failed: {response.status_code} {response.text[:300]}"
        )

    data = response.json() if response.content else {}
    if data.get("status") not in (None, "success"):
        raise WebinarMessagingError(f"MSG91 WhatsApp response error: {data}")
    request_id = data.get("request_id") or data.get("id") or ""
    return {"ok": True, "provider_message_id": str(request_id)}
