from __future__ import annotations

from typing import Optional

from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException

from k8s_cmp_assistant.config import Settings

class NamespaceNotAllowedError(Exception):
    """Raised when a namespace is not allowed by the settings."""

class KubernetesOperationsError(Exception):
    """Raised when a Kubernetes operation fails."""

def _ensure_namespace_allowed(settings: Settings, namespace: str) -> None:
    if not settings.is_namespace_allowed(namespace):
        raise NamespaceNotAllowedError(
            f"Access to namespace '{namespace}' is not allowed by current configuration."
        )
    
def list_pods(settings: Settings, core_v1_api: CoreV1Api, namespace: Optional[str] = None) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_pod(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list pods in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"An unexpected error occurred while listing pods in namespace '{namespace}': {exc}"
        ) from exc
    pods: list[dict[str, Any]] = []
    for item in response.items:
        container_statuses = item.status.container_statuses or []
        ready_count = sum(1 for status in container_statuses if status.ready)
        total_count = len(container_statuses)
        pod_info = {
            "name": item.metadata.name,
            "namespace": item.metadata.namespace,
            "status": item.status.phase,
            "node": item.spec.node_name,
            "restart_count": sum(status.restart_count for status in container_statuses),
            "started_at": (item.status.start_time.isoformat() if item.status.start_time else None),
            "labels": item.metadata.labels,
            "ip": item.status.pod_ip,
            "created_at": item.metadata.creation_timestamp,
            "ready_containers": f"{ready_count}/{total_count}",
            "containers": [container.name for container in item.spec.containers],
        }
        pods.append(pod_info)
    return {
        "namespace": namespace,
        "pod_count": len(pods),
        "pods": pods    
    }

def get_pod_logs(
        namespace: str,
        pod_name: str,
        api: CoreV1Api,
        settings: Settings,
        tail_lines: int | None = None,
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    if tail_lines is not None:
        if tail_lines < 1 or tail_lines > settings.max_log_tail_lines:
            raise ValueError(
                f"tail_lines must be between 1 and {settings.max_log_tail_lines}"
            )
    else:
        tail_lines = settings.default_log_tail_lines
    try:
        logs = api.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines,
            timestamps=True,
        )
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to get logs for pod '{pod_name}' in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"An unexpected error occurred while getting logs for pod '{pod_name}' in namespace '{namespace}': {exc}"
        ) from exc
    return {
        "pod_name": pod_name,
        "namespace": namespace,
        "logs": logs,
    }