from __future__ import annotations

from typing import Any

from kubernetes.client import AppsV1Api
from kubernetes.client.exceptions import ApiException

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.pods import (
    KubernetesOperationsError,
    NamespaceAccessError,
    _ensure_namespace_allowed,
)


def list_deployments(settings: Settings, api: AppsV1Api, namespace: str) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_deployment(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list deployments in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing deployments in namespace '{namespace}': {exc}"
        ) from exc

    deployments: list[dict[str, Any]] = []
    for item in response.items:
        status = item.status
        # Grab the first container image as a representative image
        containers = item.spec.template.spec.containers or []
        image = containers[0].image if containers else None

        deployments.append({
            "name": item.metadata.name,
            "namespace": item.metadata.namespace,
            "replicas": item.spec.replicas or 0,
            "ready_replicas": status.ready_replicas or 0,
            "available_replicas": status.available_replicas or 0,
            "updated_replicas": status.updated_replicas or 0,
            "image": image,
            "created_at": item.metadata.creation_timestamp.isoformat()
            if item.metadata.creation_timestamp
            else None,
            "labels": item.metadata.labels,
        })

    return {
        "namespace": namespace,
        "deployment_count": len(deployments),
        "deployments": deployments,
    }


def describe_deployment(
    settings: Settings, api: AppsV1Api, namespace: str, deployment_name: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        dep = api.read_namespaced_deployment(name=deployment_name, namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to describe deployment '{deployment_name}' in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error describing deployment '{deployment_name}': {exc}"
        ) from exc

    status = dep.status
    containers = dep.spec.template.spec.containers or []
    container_specs = [
        {
            "name": c.name,
            "image": c.image,
            "resources": {
                "requests": c.resources.requests or {} if c.resources else {},
                "limits": c.resources.limits or {} if c.resources else {},
            },
            "ports": [
                {"name": p.name, "container_port": p.container_port, "protocol": p.protocol}
                for p in (c.ports or [])
            ],
        }
        for c in containers
    ]

    conditions = [
        {
            "type": cond.type,
            "status": cond.status,
            "reason": cond.reason,
            "message": cond.message,
            "last_update_time": cond.last_update_time.isoformat()
            if cond.last_update_time
            else None,
        }
        for cond in (status.conditions or [])
    ]

    return {
        "name": dep.metadata.name,
        "namespace": dep.metadata.namespace,
        "replicas": dep.spec.replicas or 0,
        "ready_replicas": status.ready_replicas or 0,
        "available_replicas": status.available_replicas or 0,
        "updated_replicas": status.updated_replicas or 0,
        "strategy": dep.spec.strategy.type if dep.spec.strategy else None,
        "selector": dep.spec.selector.match_labels if dep.spec.selector else {},
        "labels": dep.metadata.labels,
        "annotations": dep.metadata.annotations,
        "created_at": dep.metadata.creation_timestamp.isoformat()
        if dep.metadata.creation_timestamp
        else None,
        "container_specs": container_specs,
        "conditions": conditions,
    }
