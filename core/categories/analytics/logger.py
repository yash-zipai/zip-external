import json
import logging
import sys
from datetime import datetime
from typing import Any

analytics_logger = logging.getLogger("zipai.analytics")

if not analytics_logger.handlers:
    analytics_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter("%(message)s")

    handler.setFormatter(formatter)

    analytics_logger.addHandler(handler)

analytics_logger.propagate = False


def log_event(
    event_type: str,
    category: str,
    action: str,
    user_id: str | None = None,
    session_id: str | None = None,
    resource_id: str | None = None,
    zipcode: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    """
    Log analytics events in JSON format.

    Example:
        log_event(
            event_type="house_view",
            category="property",
            action="view",
            resource_id="HOUSE123",
            zipcode="90001"
        )
    """

    event = {
        "timestamp": datetime.utcnow().isoformat(),

        "event_type": event_type,

        "category": category,

        "action": action,

        "user_id": user_id,

        "session_id": session_id,

        "resource_id": resource_id,

        "zipcode": zipcode,

        "metadata": metadata or {}
    }

    analytics_logger.info(json.dumps(event))