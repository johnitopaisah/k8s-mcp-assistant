from __future__ import annotations

from typing import Any, Optional

from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException

from k8s_mcp_assistant.config import Settings


class NamespaceAccessError(Exception):
    """Raised when a namespace is not permitted by the current settings."""


class KubernetesOperationsError(Exception):
    """Raised when a Kubernetes API operation fails."""


def _ensure_namespace_allowed(settings: Settings, namespace: str) -> None:
    if not settings.is_namespace_allowed(namespace):
        raise NamespaceAccessError(
            f"Access to namespace '{namespace}' is not allowed by current configuration."
        )


def list_pods(settings: Settings, api: CoreV1Api, namespace: str) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_pod(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list pods in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing pods in namespace '{namespace}': {exc}"
        ) from exc

    pods: list[dict[str, Any]] = []
    for item in response.items:
        container_statuses = item.status.container_statuses or []
        ready_count = sum(1 for s in container_statuses if s.ready)
        total_count = len(container_statuses)
        pods.append({
            "name": item.metadata.name,
            "namespace": item.metadata.namespace,
            "status": item.status.phase,
            "node": item.spec.node_name,
            "restart_count": sum(s.restart_count for s in container_statuses),
            "started_at": item.status.start_time.isoformat() if item.status.start_time else None,
            "labels": item.metadata.labels,
            "ip": item.status.pod_ip,
            "created_at": item.metadata.creation_timestamp.isoformat()
            if item.metadata.creation_timestamp
            else None,
            "ready_containers": f"{ready_count}/{total_count}",
            "containers": [c.name for c in item.spec.containers],
        })

    return {"namespace": namespace, "pod_count": len(pods), "pods": pods}


def describe_pod(
    settings: Settings, api: CoreV1Api, namespace: str, pod_name: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        pod = api.read_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to describe pod '{pod_name}' in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error describing pod '{pod_name}' in namespace '{namespace}': {exc}"
        ) from exc

    conditions = [
        {
            "type": c.type,
            "status": c.status,
            "reason": c.reason,
            "message": c.message,
            "last_transition_time": c.last_transition_time.isoformat()
            if c.last_transition_time
            else None,
        }
        for c in (pod.status.conditions or [])
    ]

    container_statuses = []
    for cs in pod.status.container_statuses or []:
        state = cs.state
        state_info: dict[str, Any] = {}
        if state.running:
            state_info = {
                "running": {
                    "started_at": state.running.started_at.isoformat()
                    if state.running.started_at
                    else None
                }
            }
        elif state.waiting:
            state_info = {
                "waiting": {"reason": state.waiting.reason, "message": state.waiting.message}
            }
        elif state.terminated:
            state_info = {
                "terminated": {
                    "reason": state.terminated.reason,
                    "exit_code": state.terminated.exit_code,
                    "message": state.terminated.message,
                }
            }
        container_statuses.append({
            "name": cs.name,
            "ready": cs.ready,
            "restart_count": cs.restart_count,
            "image": cs.image,
            "state": state_info,
        })

    container_specs = []
    for c in pod.spec.containers or []:
        resources = {}
        if c.resources:
            resources = {
                "requests": c.resources.requests or {},
                "limits": c.resources.limits or {},
            }
        ports = [
            {"name": p.name, "container_port": p.container_port, "protocol": p.protocol}
            for p in (c.ports or [])
        ]
        container_specs.append({
            "name": c.name,
            "image": c.image,
            "resources": resources,
            "ports": ports,
        })

    events: list[dict[str, Any]] = []
    try:
        event_list = api.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}",
        )
        for e in event_list.items:
            events.append({
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "count": e.count,
                "first_time": e.first_timestamp.isoformat() if e.first_timestamp else None,
                "last_time": e.last_timestamp.isoformat() if e.last_timestamp else None,
                "source": e.source.component if e.source else None,
            })
    except Exception:
        pass  # Events are best-effort; never fail the whole describe

    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "node": pod.spec.node_name,
        "status": pod.status.phase,
        "pod_ip": pod.status.pod_ip,
        "host_ip": pod.status.host_ip,
        "created_at": pod.metadata.creation_timestamp.isoformat()
        if pod.metadata.creation_timestamp
        else None,
        "labels": pod.metadata.labels,
        "annotations": pod.metadata.annotations,
        "conditions": conditions,
        "container_specs": container_specs,
        "container_statuses": container_statuses,
        "events": events,
    }


def get_pod_logs(
    settings: Settings,
    api: CoreV1Api,
    namespace: str,
    pod_name: str,
    container_name: Optional[str] = None,
    tail_lines: Optional[int] = None,
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)

    if tail_lines is not None:
        if tail_lines < 1 or tail_lines > settings.max_log_tail_lines:
            raise KubernetesOperationsError(
                f"tail_lines must be between 1 and {settings.max_log_tail_lines}, got {tail_lines}."
            )
    else:
        tail_lines = settings.default_log_tail_lines

    try:
        logs = api.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container_name,
            tail_lines=tail_lines,
            timestamps=True,
        )
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to get logs for pod '{pod_name}' in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error getting logs for pod '{pod_name}' in namespace '{namespace}': {exc}"
        ) from exc

    return {
        "pod_name": pod_name,
        "namespace": namespace,
        "container": container_name,
        "logs": logs,
    }
