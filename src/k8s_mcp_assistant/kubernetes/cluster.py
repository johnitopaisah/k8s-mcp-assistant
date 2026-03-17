from __future__ import annotations

from typing import Any

from kubernetes import client as k8s_client
from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.pods import KubernetesOperationsError


# ── Namespaces ─────────────────────────────────────────────────────────────────

def list_namespaces(settings: Settings, api: CoreV1Api) -> dict[str, Any]:
    """List all namespaces in the cluster."""
    try:
        response = api.list_namespace()
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list namespaces: {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing namespaces: {exc}"
        ) from exc

    namespaces: list[dict[str, Any]] = []
    for item in response.items:
        namespaces.append({
            "name": item.metadata.name,
            "status": item.status.phase if item.status else None,
            "labels": item.metadata.labels,
            "annotations": item.metadata.annotations,
            "created_at": item.metadata.creation_timestamp.isoformat()
            if item.metadata.creation_timestamp
            else None,
        })

    return {
        "namespace_count": len(namespaces),
        "namespaces": namespaces,
    }


# ── Nodes ──────────────────────────────────────────────────────────────────────

def list_nodes(settings: Settings, api: CoreV1Api) -> dict[str, Any]:
    """List all nodes with status, roles, capacity, allocatable resources and taints."""
    try:
        response = api.list_node()
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list nodes: {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing nodes: {exc}"
        ) from exc

    nodes: list[dict[str, Any]] = []
    for item in response.items:
        labels = item.metadata.labels or {}
        roles = [
            key.split("/")[1]
            for key in labels
            if key.startswith("node-role.kubernetes.io/")
        ] or ["worker"]

        conditions = item.status.conditions or []
        ready_status = next(
            (c.status for c in conditions if c.type == "Ready"), "Unknown"
        )

        taints = [
            {"key": t.key, "effect": t.effect, "value": t.value}
            for t in (item.spec.taints or [])
        ]

        nodes.append({
            "name": item.metadata.name,
            "roles": roles,
            "ready": ready_status,
            "labels": labels,
            "os_image": item.status.node_info.os_image if item.status.node_info else None,
            "kernel_version": item.status.node_info.kernel_version
            if item.status.node_info else None,
            "container_runtime": item.status.node_info.container_runtime_version
            if item.status.node_info else None,
            "kubelet_version": item.status.node_info.kubelet_version
            if item.status.node_info else None,
            "capacity": dict(item.status.capacity) if item.status.capacity else {},
            "allocatable": dict(item.status.allocatable) if item.status.allocatable else {},
            "taints": taints,
            "unschedulable": item.spec.unschedulable or False,
            "created_at": item.metadata.creation_timestamp.isoformat()
            if item.metadata.creation_timestamp else None,
        })

    return {
        "node_count": len(nodes),
        "nodes": nodes,
    }


def describe_node(settings: Settings, api: CoreV1Api, node_name: str) -> dict[str, Any]:
    """Full node detail including conditions, addresses, system info, capacity and events."""
    try:
        node = api.read_node(name=node_name)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to describe node '{node_name}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error describing node '{node_name}': {exc}"
        ) from exc

    labels = node.metadata.labels or {}
    roles = [
        key.split("/")[1]
        for key in labels
        if key.startswith("node-role.kubernetes.io/")
    ] or ["worker"]

    conditions = [
        {
            "type": c.type,
            "status": c.status,
            "reason": c.reason,
            "message": c.message,
            "last_heartbeat_time": c.last_heartbeat_time.isoformat()
            if c.last_heartbeat_time else None,
            "last_transition_time": c.last_transition_time.isoformat()
            if c.last_transition_time else None,
        }
        for c in (node.status.conditions or [])
    ]

    addresses = [
        {"type": a.type, "address": a.address}
        for a in (node.status.addresses or [])
    ]

    taints = [
        {"key": t.key, "effect": t.effect, "value": t.value}
        for t in (node.spec.taints or [])
    ]

    events: list[dict[str, Any]] = []
    try:
        event_list = api.list_event_for_all_namespaces(
            field_selector=(
                f"involvedObject.name={node_name},"
                f"involvedObject.kind=Node"
            )
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
        pass

    node_info = node.status.node_info
    return {
        "name": node.metadata.name,
        "roles": roles,
        "labels": labels,
        "annotations": node.metadata.annotations,
        "created_at": node.metadata.creation_timestamp.isoformat()
        if node.metadata.creation_timestamp else None,
        "unschedulable": node.spec.unschedulable or False,
        "taints": taints,
        "conditions": conditions,
        "addresses": addresses,
        "capacity": dict(node.status.capacity) if node.status.capacity else {},
        "allocatable": dict(node.status.allocatable) if node.status.allocatable else {},
        "system_info": {
            "os_image": node_info.os_image if node_info else None,
            "kernel_version": node_info.kernel_version if node_info else None,
            "os": node_info.operating_system if node_info else None,
            "architecture": node_info.architecture if node_info else None,
            "container_runtime": node_info.container_runtime_version if node_info else None,
            "kubelet_version": node_info.kubelet_version if node_info else None,
            "kube_proxy_version": node_info.kube_proxy_version if node_info else None,
        },
        "events": events,
    }


# ── Cluster info ───────────────────────────────────────────────────────────────

def get_cluster_info(
    settings: Settings, version_api: k8s_client.VersionApi
) -> dict[str, Any]:
    """Retrieve cluster server version and build info."""
    try:
        version = version_api.get_code()
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to get cluster version info: {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error getting cluster info: {exc}"
        ) from exc

    return {
        "git_version": version.git_version,
        "major": version.major,
        "minor": version.minor,
        "platform": version.platform,
        "go_version": version.go_version,
        "build_date": version.build_date,
        "compiler": version.compiler,
    }


# ── API Resources ──────────────────────────────────────────────────────────────

def list_api_resources(
    settings: Settings, api_client: k8s_client.ApiClient
) -> dict[str, Any]:
    """
    List all available API resource types across all groups and versions.
    Equivalent to `kubectl api-resources`.
    """
    resources: list[dict[str, Any]] = []

    # Core API group (v1)
    try:
        core_api = k8s_client.CoreV1Api(api_client)
        core_list = core_api.get_api_resources()
        for r in core_list.resources:
            if "/" not in r.name:
                resources.append({
                    "name": r.name,
                    "kind": r.kind,
                    "namespaced": r.namespaced,
                    "group": "",
                    "version": "v1",
                    "verbs": list(r.verbs) if r.verbs else [],
                    "short_names": list(r.short_names) if r.short_names else [],
                })
    except Exception:
        pass

    # All named API groups
    try:
        apis_api = k8s_client.ApisApi(api_client)
        api_groups = apis_api.get_api_versions()
        for group in api_groups.groups:
            preferred = group.preferred_version
            if not preferred:
                continue
            try:
                # Use the dynamic client to fetch resource list for this group version
                path = f"/apis/{preferred.group_version}"
                (data, status_code, _) = api_client.call_api(
                    path,
                    "GET",
                    response_type="V1APIResourceList",
                    auth_settings=["BearerToken"],
                    _return_http_data_only=True,
                )
                for r in data.resources:
                    if "/" not in r.name:
                        resources.append({
                            "name": r.name,
                            "kind": r.kind,
                            "namespaced": r.namespaced,
                            "group": group.name,
                            "version": preferred.version,
                            "verbs": list(r.verbs) if r.verbs else [],
                            "short_names": list(r.short_names) if r.short_names else [],
                        })
            except Exception:
                continue
    except Exception:
        pass

    resources.sort(key=lambda x: (x["group"], x["name"]))

    return {
        "resource_count": len(resources),
        "resources": resources,
    }
