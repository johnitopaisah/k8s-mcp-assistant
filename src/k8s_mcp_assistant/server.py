from __future__ import annotations

import json
import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.client import (
    KubernetesClientError,
    get_core_v1_api,
    get_apps_v1_api,
)
from k8s_mcp_assistant.kubernetes.pods import (
    KubernetesOperationsError,
    NamespaceAccessError,
    list_pods,
    describe_pod,
    get_pod_logs,
)
from k8s_mcp_assistant.kubernetes.deployments import (
    list_deployments,
    describe_deployment,
)
from k8s_mcp_assistant.kubernetes.services import list_services
from k8s_mcp_assistant.kubernetes.events import list_events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings.load()
mcp = FastMCP("k8s-mcp-assistant")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ok(data: dict[str, Any]) -> str:
    return json.dumps({"ok": True, "data": data}, indent=2)


def _err(message: str, error_type: str = "error") -> str:
    return json.dumps({"ok": False, "error_type": error_type, "message": message}, indent=2)


def _handle(exc: Exception, context: str) -> str:
    if isinstance(exc, NamespaceAccessError):
        return _err(str(exc), error_type="namespace_access_denied")
    if isinstance(exc, KubernetesClientError):
        return _err(str(exc), error_type="kubernetes_client_error")
    if isinstance(exc, KubernetesOperationsError):
        return _err(str(exc), error_type="kubernetes_operations_error")
    logger.exception("Unhandled error in %s", context)
    return _err(f"Unhandled server error in {context}: {exc}", error_type="internal_server_error")


# ── Health ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def health_check() -> str:
    """
    Verify the server is running and show current configuration (read-only mode,
    allowed namespaces).
    """
    return _ok({
        "server": "k8s-mcp-assistant",
        "read_only": settings.read_only,
        "allowed_namespaces": settings.allowed_namespaces or "all",
    })


# ── Pod tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_pods_tool(namespace: str) -> str:
    """
    List all pods in a Kubernetes namespace with their status, node, restart count,
    and ready container ratio.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        api = get_core_v1_api(settings)
        return _ok(list_pods(namespace=namespace, api=api, settings=settings))
    except Exception as exc:
        return _handle(exc, "list_pods_tool")


@mcp.tool()
def describe_pod_tool(namespace: str, pod_name: str) -> str:
    """
    Describe a specific pod including conditions, container statuses, resource
    requests/limits, and events. Especially useful for diagnosing pods stuck in
    Pending, CrashLoopBackOff, ImagePullBackOff, or other non-Running states.
    Args:
        namespace: Kubernetes namespace of the pod.
        pod_name: Name of the pod to describe.
    """
    try:
        api = get_core_v1_api(settings)
        return _ok(describe_pod(namespace=namespace, pod_name=pod_name, api=api, settings=settings))
    except Exception as exc:
        return _handle(exc, "describe_pod_tool")


@mcp.tool()
def get_pod_logs_tool(
    namespace: str,
    pod_name: str,
    container_name: Optional[str] = None,
    tail_lines: int = 100,
) -> str:
    """
    Retrieve logs from a pod. Supports multi-container pods via container_name.
    Args:
        namespace: Kubernetes namespace of the pod.
        pod_name: Name of the pod.
        container_name: Name of the container (required for multi-container pods).
        tail_lines: Number of lines to return from the end of the log (default 100).
    """
    try:
        api = get_core_v1_api(settings)
        return _ok(
            get_pod_logs(
                namespace=namespace,
                pod_name=pod_name,
                container_name=container_name,
                api=api,
                settings=settings,
                tail_lines=tail_lines,
            )
        )
    except Exception as exc:
        return _handle(exc, "get_pod_logs_tool")


# ── Deployment tools ───────────────────────────────────────────────────────────

@mcp.tool()
def list_deployments_tool(namespace: str) -> str:
    """
    List all deployments in a Kubernetes namespace with replica counts and image info.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        api = get_apps_v1_api(settings)
        return _ok(list_deployments(namespace=namespace, api=api, settings=settings))
    except Exception as exc:
        return _handle(exc, "list_deployments_tool")


@mcp.tool()
def describe_deployment_tool(namespace: str, deployment_name: str) -> str:
    """
    Describe a specific deployment including replica status, strategy, container
    specs, and conditions. Useful for diagnosing rollout failures or unavailable pods.
    Args:
        namespace: Kubernetes namespace of the deployment.
        deployment_name: Name of the deployment to describe.
    """
    try:
        api = get_apps_v1_api(settings)
        return _ok(
            describe_deployment(
                namespace=namespace, deployment_name=deployment_name, api=api, settings=settings
            )
        )
    except Exception as exc:
        return _handle(exc, "describe_deployment_tool")


# ── Service tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_services_tool(namespace: str) -> str:
    """
    List all services in a Kubernetes namespace including type, cluster IP,
    external IP, and port mappings.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        api = get_core_v1_api(settings)
        return _ok(list_services(namespace=namespace, api=api, settings=settings))
    except Exception as exc:
        return _handle(exc, "list_services_tool")


# ── Event tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_events_tool(namespace: str, involved_object: Optional[str] = None) -> str:
    """
    List events in a Kubernetes namespace, sorted newest first. Optionally filter
    by the name of the involved object (e.g. a specific pod or deployment name).
    Args:
        namespace: Target Kubernetes namespace.
        involved_object: Optional name of the resource to filter events for.
    """
    try:
        api = get_core_v1_api(settings)
        field_selector = (
            f"involvedObject.name={involved_object}" if involved_object else None
        )
        return _ok(
            list_events(
                namespace=namespace,
                api=api,
                settings=settings,
                field_selector=field_selector,
            )
        )
    except Exception as exc:
        return _handle(exc, "list_events_tool")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("Starting k8s-mcp-assistant server...")
    logger.info("Read-only mode: %s", settings.read_only)
    logger.info(
        "Allowed namespaces: %s",
        ", ".join(settings.allowed_namespaces) if settings.allowed_namespaces else "all",
    )
    mcp.run()


if __name__ == "__main__":
    main()
