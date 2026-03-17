from __future__ import annotations

from typing import Any, Optional

from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.pods import (
    KubernetesOperationsError,
    _ensure_namespace_allowed,
)


def list_events(
    settings: Settings,
    api: CoreV1Api,
    namespace: str,
    field_selector: Optional[str] = None,
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_event(
            namespace=namespace,
            field_selector=field_selector,
        )
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list events in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing events in namespace '{namespace}': {exc}"
        ) from exc

    events: list[dict[str, Any]] = []
    for e in response.items:
        events.append({
            "type": e.type,
            "reason": e.reason,
            "message": e.message,
            "count": e.count,
            "first_time": e.first_timestamp.isoformat() if e.first_timestamp else None,
            "last_time": e.last_timestamp.isoformat() if e.last_timestamp else None,
            "source": e.source.component if e.source else None,
            "involved_object": e.involved_object.name if e.involved_object else None,
            "involved_object_kind": e.involved_object.kind if e.involved_object else None,
        })

    # Sort by last_time descending so newest events come first
    events.sort(key=lambda x: x["last_time"] or "", reverse=True)

    return {
        "namespace": namespace,
        "event_count": len(events),
        "events": events,
    }
