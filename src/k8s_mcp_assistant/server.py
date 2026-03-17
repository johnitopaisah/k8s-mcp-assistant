from __future__ import annotations

import json
import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.client import (
    KubernetesClientError,
    get_api_client,
    get_core_v1_api,
    get_apps_v1_api,
    get_batch_v1_api,
    get_version_api,
)
from k8s_mcp_assistant.kubernetes.pods import (
    KubernetesOperationsError,
    NamespaceAccessError,
    list_pods,
    describe_pod,
    get_pod_logs,
)
from k8s_mcp_assistant.kubernetes.deployments import list_deployments, describe_deployment
from k8s_mcp_assistant.kubernetes.services import list_services
from k8s_mcp_assistant.kubernetes.events import list_events
from k8s_mcp_assistant.kubernetes.cluster import (
    list_namespaces,
    list_nodes,
    describe_node,
    get_cluster_info,
    list_api_resources,
)
from k8s_mcp_assistant.kubernetes.workloads import (
    list_statefulsets,
    describe_statefulset,
    list_daemonsets,
    describe_daemonset,
    list_replicasets,
    describe_replicaset,
    list_jobs,
    describe_job,
    list_cronjobs,
    describe_cronjob,
)

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
    """Verify the server is running and show current configuration."""
    return _ok({
        "server": "k8s-mcp-assistant",
        "read_only": settings.read_only,
        "allowed_namespaces": settings.allowed_namespaces or "all",
    })


# ── Cluster-wide tools ─────────────────────────────────────────────────────────

@mcp.tool()
def list_namespaces_tool() -> str:
    """
    List all namespaces in the cluster with their status, labels and creation time.
    Cluster-scoped — no namespace argument needed.
    """
    try:
        return _ok(list_namespaces(settings=settings, api=get_core_v1_api(settings)))
    except Exception as exc:
        return _handle(exc, "list_namespaces_tool")


@mcp.tool()
def list_nodes_tool() -> str:
    """
    List all nodes with roles, ready status, capacity, allocatable resources,
    kubelet version, OS image and taints. Cluster-scoped.
    """
    try:
        return _ok(list_nodes(settings=settings, api=get_core_v1_api(settings)))
    except Exception as exc:
        return _handle(exc, "list_nodes_tool")


@mcp.tool()
def describe_node_tool(node_name: str) -> str:
    """
    Full node detail: conditions, addresses, system info, capacity vs allocatable,
    taints and node-level events. Useful for diagnosing pressure or cordoned nodes.
    Args:
        node_name: Name of the node to describe.
    """
    try:
        return _ok(describe_node(settings=settings, api=get_core_v1_api(settings), node_name=node_name))
    except Exception as exc:
        return _handle(exc, "describe_node_tool")


@mcp.tool()
def get_cluster_info_tool() -> str:
    """
    Cluster server version and build info: git version, major/minor, platform,
    Go version, build date. Equivalent to `kubectl version --short`.
    """
    try:
        return _ok(get_cluster_info(settings=settings, version_api=get_version_api(settings)))
    except Exception as exc:
        return _handle(exc, "get_cluster_info_tool")


@mcp.tool()
def list_api_resources_tool() -> str:
    """
    List all API resource types across every group and version: kind, scope,
    verbs, short names. Equivalent to `kubectl api-resources`.
    """
    try:
        return _ok(list_api_resources(settings=settings, api_client=get_api_client(settings)))
    except Exception as exc:
        return _handle(exc, "list_api_resources_tool")


# ── Pod tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_pods_tool(namespace: str) -> str:
    """
    List all pods in a namespace with status, node, restart count and ready ratio.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        return _ok(list_pods(namespace=namespace, api=get_core_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "list_pods_tool")


@mcp.tool()
def describe_pod_tool(namespace: str, pod_name: str) -> str:
    """
    Full pod detail: conditions, container statuses, resource requests/limits,
    events. Useful for Pending, CrashLoopBackOff, ImagePullBackOff diagnosis.
    Args:
        namespace: Kubernetes namespace of the pod.
        pod_name: Name of the pod to describe.
    """
    try:
        return _ok(describe_pod(namespace=namespace, pod_name=pod_name,
                                api=get_core_v1_api(settings), settings=settings))
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
    Retrieve pod logs. Supports multi-container pods via container_name.
    Args:
        namespace: Kubernetes namespace of the pod.
        pod_name: Name of the pod.
        container_name: Container name (required for multi-container pods).
        tail_lines: Lines from end of log to return (default 100).
    """
    try:
        return _ok(get_pod_logs(namespace=namespace, pod_name=pod_name,
                                container_name=container_name,
                                api=get_core_v1_api(settings), settings=settings,
                                tail_lines=tail_lines))
    except Exception as exc:
        return _handle(exc, "get_pod_logs_tool")


# ── Deployment tools ───────────────────────────────────────────────────────────

@mcp.tool()
def list_deployments_tool(namespace: str) -> str:
    """
    List all deployments in a namespace with replica counts and image info.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        return _ok(list_deployments(namespace=namespace, api=get_apps_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "list_deployments_tool")


@mcp.tool()
def describe_deployment_tool(namespace: str, deployment_name: str) -> str:
    """
    Full deployment detail: replica status, strategy, container specs, conditions.
    Args:
        namespace: Kubernetes namespace of the deployment.
        deployment_name: Name of the deployment.
    """
    try:
        return _ok(describe_deployment(namespace=namespace, deployment_name=deployment_name,
                                       api=get_apps_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "describe_deployment_tool")


# ── StatefulSet tools ──────────────────────────────────────────────────────────

@mcp.tool()
def list_statefulsets_tool(namespace: str) -> str:
    """
    List all StatefulSets in a namespace with replica counts, service name and image.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        return _ok(list_statefulsets(namespace=namespace, api=get_apps_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "list_statefulsets_tool")


@mcp.tool()
def describe_statefulset_tool(namespace: str, name: str) -> str:
    """
    Full StatefulSet detail: replicas, pod management policy, update strategy,
    volume claim templates, container specs and conditions.
    Args:
        namespace: Kubernetes namespace of the StatefulSet.
        name: Name of the StatefulSet.
    """
    try:
        return _ok(describe_statefulset(namespace=namespace, name=name,
                                        api=get_apps_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "describe_statefulset_tool")


# ── DaemonSet tools ────────────────────────────────────────────────────────────

@mcp.tool()
def list_daemonsets_tool(namespace: str) -> str:
    """
    List all DaemonSets in a namespace with desired, current, ready and
    available node counts.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        return _ok(list_daemonsets(namespace=namespace, api=get_apps_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "list_daemonsets_tool")


@mcp.tool()
def describe_daemonset_tool(namespace: str, name: str) -> str:
    """
    Full DaemonSet detail: node counts, update strategy, selector, node selector,
    tolerations, container specs and conditions.
    Args:
        namespace: Kubernetes namespace of the DaemonSet.
        name: Name of the DaemonSet.
    """
    try:
        return _ok(describe_daemonset(namespace=namespace, name=name,
                                      api=get_apps_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "describe_daemonset_tool")


# ── ReplicaSet tools ───────────────────────────────────────────────────────────

@mcp.tool()
def list_replicasets_tool(namespace: str) -> str:
    """
    List all ReplicaSets in a namespace with desired/ready/available counts,
    image and owner references (shows which Deployment owns each ReplicaSet).
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        return _ok(list_replicasets(namespace=namespace, api=get_apps_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "list_replicasets_tool")


@mcp.tool()
def describe_replicaset_tool(namespace: str, name: str) -> str:
    """
    Full ReplicaSet detail: replica counts, selector, owner references,
    container specs and conditions.
    Args:
        namespace: Kubernetes namespace of the ReplicaSet.
        name: Name of the ReplicaSet.
    """
    try:
        return _ok(describe_replicaset(namespace=namespace, name=name,
                                       api=get_apps_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "describe_replicaset_tool")


# ── Job tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_jobs_tool(namespace: str) -> str:
    """
    List all Jobs in a namespace with completion status, active/succeeded/failed
    counts, parallelism, start and completion times.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        return _ok(list_jobs(namespace=namespace, api=get_batch_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "list_jobs_tool")


@mcp.tool()
def describe_job_tool(namespace: str, name: str) -> str:
    """
    Full Job detail: completions, parallelism, backoff limit, active deadline,
    TTL after finished, start/completion times, container specs and conditions.
    Args:
        namespace: Kubernetes namespace of the Job.
        name: Name of the Job.
    """
    try:
        return _ok(describe_job(namespace=namespace, name=name,
                                api=get_batch_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "describe_job_tool")


# ── CronJob tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_cronjobs_tool(namespace: str) -> str:
    """
    List all CronJobs in a namespace with schedule, suspend status, active job
    count and last schedule/successful time.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        return _ok(list_cronjobs(namespace=namespace, api=get_batch_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "list_cronjobs_tool")


@mcp.tool()
def describe_cronjob_tool(namespace: str, name: str) -> str:
    """
    Full CronJob detail: schedule, timezone, concurrency policy, suspend,
    history limits, active jobs, job spec (completions, parallelism, backoff),
    container specs.
    Args:
        namespace: Kubernetes namespace of the CronJob.
        name: Name of the CronJob.
    """
    try:
        return _ok(describe_cronjob(namespace=namespace, name=name,
                                    api=get_batch_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "describe_cronjob_tool")


# ── Service tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_services_tool(namespace: str) -> str:
    """
    List all services in a namespace with type, cluster IP, external IP and ports.
    Args:
        namespace: Target Kubernetes namespace.
    """
    try:
        return _ok(list_services(namespace=namespace, api=get_core_v1_api(settings), settings=settings))
    except Exception as exc:
        return _handle(exc, "list_services_tool")


# ── Event tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_events_tool(namespace: str, involved_object: Optional[str] = None) -> str:
    """
    List events in a namespace, sorted newest first. Optionally filter by
    the name of an involved object (pod, deployment, node, etc.).
    Args:
        namespace: Target Kubernetes namespace.
        involved_object: Optional resource name to filter events for.
    """
    try:
        field_selector = (
            f"involvedObject.name={involved_object}" if involved_object else None
        )
        return _ok(list_events(namespace=namespace, api=get_core_v1_api(settings),
                               settings=settings, field_selector=field_selector))
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
