from __future__ import annotations

from typing import Any

from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.pods import (
    KubernetesOperationsError,
    _ensure_namespace_allowed,
)


def list_services(settings: Settings, api: CoreV1Api, namespace: str) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_service(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list services in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing services in namespace '{namespace}': {exc}"
        ) from exc

    services: list[dict[str, Any]] = []
    for item in response.items:
        spec = item.spec
        # External IP: LoadBalancer ingress or externalIPs
        external_ip = None
        if item.status.load_balancer and item.status.load_balancer.ingress:
            ingress = item.status.load_balancer.ingress[0]
            external_ip = ingress.hostname or ingress.ip
        elif spec.external_i_ps:
            external_ip = ", ".join(spec.external_i_ps)

        ports = [
            {
                "name": p.name,
                "port": p.port,
                "target_port": str(p.target_port) if p.target_port else None,
                "protocol": p.protocol,
                "node_port": p.node_port,
            }
            for p in (spec.ports or [])
        ]

        services.append({
            "name": item.metadata.name,
            "namespace": item.metadata.namespace,
            "type": spec.type,
            "cluster_ip": spec.cluster_ip,
            "external_ip": external_ip,
            "ports": ports,
            "selector": spec.selector,
            "created_at": item.metadata.creation_timestamp.isoformat()
            if item.metadata.creation_timestamp
            else None,
        })

    return {
        "namespace": namespace,
        "service_count": len(services),
        "services": services,
    }
