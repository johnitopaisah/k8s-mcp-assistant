from __future__ import annotations

from typing import Any, Optional

from kubernetes.client import AppsV1Api, BatchV1Api
from kubernetes.client.exceptions import ApiException

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.pods import (
    KubernetesOperationsError,
    _ensure_namespace_allowed,
)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _container_specs(containers: list) -> list[dict[str, Any]]:
    specs = []
    for c in containers or []:
        resources: dict[str, Any] = {}
        if c.resources:
            resources = {
                "requests": c.resources.requests or {},
                "limits": c.resources.limits or {},
            }
        ports = [
            {"name": p.name, "container_port": p.container_port, "protocol": p.protocol}
            for p in (c.ports or [])
        ]
        env = [
            {"name": e.name, "value": e.value}
            for e in (c.env or [])
            if e.value is not None
        ]
        specs.append({
            "name": c.name,
            "image": c.image,
            "resources": resources,
            "ports": ports,
            "env": env,
        })
    return specs


def _owner_references(owners: list) -> list[dict[str, Any]]:
    return [
        {"kind": o.kind, "name": o.name, "uid": o.uid}
        for o in (owners or [])
    ]


# ── StatefulSets ───────────────────────────────────────────────────────────────

def list_statefulsets(
    settings: Settings, api: AppsV1Api, namespace: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_stateful_set(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list statefulsets in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing statefulsets in '{namespace}': {exc}"
        ) from exc

    items = []
    for s in response.items:
        containers = s.spec.template.spec.containers or []
        items.append({
            "name": s.metadata.name,
            "namespace": s.metadata.namespace,
            "replicas": s.spec.replicas or 0,
            "ready_replicas": s.status.ready_replicas or 0,
            "current_replicas": s.status.current_replicas or 0,
            "updated_replicas": s.status.updated_replicas or 0,
            "service_name": s.spec.service_name,
            "image": containers[0].image if containers else None,
            "labels": s.metadata.labels,
            "created_at": s.metadata.creation_timestamp.isoformat()
            if s.metadata.creation_timestamp else None,
        })
    return {"namespace": namespace, "statefulset_count": len(items), "statefulsets": items}


def describe_statefulset(
    settings: Settings, api: AppsV1Api, namespace: str, name: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        s = api.read_namespaced_stateful_set(name=name, namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to describe statefulset '{name}' in '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error describing statefulset '{name}': {exc}"
        ) from exc

    conditions = [
        {
            "type": c.type,
            "status": c.status,
            "reason": c.reason,
            "message": c.message,
        }
        for c in (s.status.conditions or [])
    ]

    volume_claim_templates = []
    for vct in (s.spec.volume_claim_templates or []):
        resources = vct.spec.resources
        volume_claim_templates.append({
            "name": vct.metadata.name,
            "access_modes": vct.spec.access_modes or [],
            "storage_class": vct.spec.storage_class_name,
            "storage": resources.requests.get("storage") if resources and resources.requests else None,
        })

    return {
        "name": s.metadata.name,
        "namespace": s.metadata.namespace,
        "labels": s.metadata.labels,
        "annotations": s.metadata.annotations,
        "created_at": s.metadata.creation_timestamp.isoformat()
        if s.metadata.creation_timestamp else None,
        "replicas": s.spec.replicas or 0,
        "ready_replicas": s.status.ready_replicas or 0,
        "current_replicas": s.status.current_replicas or 0,
        "updated_replicas": s.status.updated_replicas or 0,
        "service_name": s.spec.service_name,
        "pod_management_policy": s.spec.pod_management_policy,
        "update_strategy": s.spec.update_strategy.type if s.spec.update_strategy else None,
        "selector": s.spec.selector.match_labels if s.spec.selector else {},
        "container_specs": _container_specs(s.spec.template.spec.containers),
        "init_container_specs": _container_specs(s.spec.template.spec.init_containers),
        "volume_claim_templates": volume_claim_templates,
        "conditions": conditions,
    }


# ── DaemonSets ─────────────────────────────────────────────────────────────────

def list_daemonsets(
    settings: Settings, api: AppsV1Api, namespace: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_daemon_set(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list daemonsets in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing daemonsets in '{namespace}': {exc}"
        ) from exc

    items = []
    for d in response.items:
        containers = d.spec.template.spec.containers or []
        items.append({
            "name": d.metadata.name,
            "namespace": d.metadata.namespace,
            "desired": d.status.desired_number_scheduled or 0,
            "current": d.status.current_number_scheduled or 0,
            "ready": d.status.number_ready or 0,
            "available": d.status.number_available or 0,
            "misscheduled": d.status.number_misscheduled or 0,
            "image": containers[0].image if containers else None,
            "labels": d.metadata.labels,
            "created_at": d.metadata.creation_timestamp.isoformat()
            if d.metadata.creation_timestamp else None,
        })
    return {"namespace": namespace, "daemonset_count": len(items), "daemonsets": items}


def describe_daemonset(
    settings: Settings, api: AppsV1Api, namespace: str, name: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        d = api.read_namespaced_daemon_set(name=name, namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to describe daemonset '{name}' in '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error describing daemonset '{name}': {exc}"
        ) from exc

    conditions = [
        {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
        for c in (d.status.conditions or [])
    ]

    return {
        "name": d.metadata.name,
        "namespace": d.metadata.namespace,
        "labels": d.metadata.labels,
        "annotations": d.metadata.annotations,
        "created_at": d.metadata.creation_timestamp.isoformat()
        if d.metadata.creation_timestamp else None,
        "desired": d.status.desired_number_scheduled or 0,
        "current": d.status.current_number_scheduled or 0,
        "ready": d.status.number_ready or 0,
        "available": d.status.number_available or 0,
        "misscheduled": d.status.number_misscheduled or 0,
        "update_strategy": d.spec.update_strategy.type if d.spec.update_strategy else None,
        "selector": d.spec.selector.match_labels if d.spec.selector else {},
        "node_selector": d.spec.template.spec.node_selector or {},
        "tolerations": [
            {"key": t.key, "operator": t.operator, "effect": t.effect, "value": t.value}
            for t in (d.spec.template.spec.tolerations or [])
        ],
        "container_specs": _container_specs(d.spec.template.spec.containers),
        "init_container_specs": _container_specs(d.spec.template.spec.init_containers),
        "conditions": conditions,
    }


# ── ReplicaSets ────────────────────────────────────────────────────────────────

def list_replicasets(
    settings: Settings, api: AppsV1Api, namespace: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_replica_set(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list replicasets in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing replicasets in '{namespace}': {exc}"
        ) from exc

    items = []
    for r in response.items:
        containers = r.spec.template.spec.containers or [] if r.spec.template else []
        items.append({
            "name": r.metadata.name,
            "namespace": r.metadata.namespace,
            "desired": r.spec.replicas or 0,
            "ready": r.status.ready_replicas or 0,
            "available": r.status.available_replicas or 0,
            "image": containers[0].image if containers else None,
            "owner_references": _owner_references(r.metadata.owner_references),
            "labels": r.metadata.labels,
            "created_at": r.metadata.creation_timestamp.isoformat()
            if r.metadata.creation_timestamp else None,
        })
    return {"namespace": namespace, "replicaset_count": len(items), "replicasets": items}


def describe_replicaset(
    settings: Settings, api: AppsV1Api, namespace: str, name: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        r = api.read_namespaced_replica_set(name=name, namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to describe replicaset '{name}' in '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error describing replicaset '{name}': {exc}"
        ) from exc

    conditions = [
        {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
        for c in (r.status.conditions or [])
    ]

    containers = r.spec.template.spec.containers if r.spec.template else []

    return {
        "name": r.metadata.name,
        "namespace": r.metadata.namespace,
        "labels": r.metadata.labels,
        "annotations": r.metadata.annotations,
        "created_at": r.metadata.creation_timestamp.isoformat()
        if r.metadata.creation_timestamp else None,
        "desired": r.spec.replicas or 0,
        "ready": r.status.ready_replicas or 0,
        "available": r.status.available_replicas or 0,
        "fully_labeled": r.status.fully_labeled_replicas or 0,
        "selector": r.spec.selector.match_labels if r.spec.selector else {},
        "owner_references": _owner_references(r.metadata.owner_references),
        "container_specs": _container_specs(containers),
        "conditions": conditions,
    }


# ── Jobs ───────────────────────────────────────────────────────────────────────

def list_jobs(
    settings: Settings, api: BatchV1Api, namespace: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_job(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list jobs in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing jobs in '{namespace}': {exc}"
        ) from exc

    items = []
    for j in response.items:
        containers = j.spec.template.spec.containers or []
        # Determine completion status
        conditions = j.status.conditions or []
        status = "Running"
        for c in conditions:
            if c.type == "Complete" and c.status == "True":
                status = "Complete"
                break
            if c.type == "Failed" and c.status == "True":
                status = "Failed"
                break

        items.append({
            "name": j.metadata.name,
            "namespace": j.metadata.namespace,
            "status": status,
            "active": j.status.active or 0,
            "succeeded": j.status.succeeded or 0,
            "failed": j.status.failed or 0,
            "completions": j.spec.completions,
            "parallelism": j.spec.parallelism,
            "image": containers[0].image if containers else None,
            "owner_references": _owner_references(j.metadata.owner_references),
            "start_time": j.status.start_time.isoformat() if j.status.start_time else None,
            "completion_time": j.status.completion_time.isoformat()
            if j.status.completion_time else None,
            "labels": j.metadata.labels,
            "created_at": j.metadata.creation_timestamp.isoformat()
            if j.metadata.creation_timestamp else None,
        })
    return {"namespace": namespace, "job_count": len(items), "jobs": items}


def describe_job(
    settings: Settings, api: BatchV1Api, namespace: str, name: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        j = api.read_namespaced_job(name=name, namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to describe job '{name}' in '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error describing job '{name}': {exc}"
        ) from exc

    conditions = [
        {
            "type": c.type,
            "status": c.status,
            "reason": c.reason,
            "message": c.message,
            "last_transition_time": c.last_transition_time.isoformat()
            if c.last_transition_time else None,
        }
        for c in (j.status.conditions or [])
    ]

    return {
        "name": j.metadata.name,
        "namespace": j.metadata.namespace,
        "labels": j.metadata.labels,
        "annotations": j.metadata.annotations,
        "created_at": j.metadata.creation_timestamp.isoformat()
        if j.metadata.creation_timestamp else None,
        "active": j.status.active or 0,
        "succeeded": j.status.succeeded or 0,
        "failed": j.status.failed or 0,
        "completions": j.spec.completions,
        "parallelism": j.spec.parallelism,
        "backoff_limit": j.spec.backoff_limit,
        "active_deadline_seconds": j.spec.active_deadline_seconds,
        "ttl_seconds_after_finished": j.spec.ttl_seconds_after_finished,
        "start_time": j.status.start_time.isoformat() if j.status.start_time else None,
        "completion_time": j.status.completion_time.isoformat()
        if j.status.completion_time else None,
        "owner_references": _owner_references(j.metadata.owner_references),
        "selector": j.spec.selector.match_labels if j.spec.selector else {},
        "container_specs": _container_specs(j.spec.template.spec.containers),
        "init_container_specs": _container_specs(j.spec.template.spec.init_containers),
        "conditions": conditions,
    }


# ── CronJobs ───────────────────────────────────────────────────────────────────

def list_cronjobs(
    settings: Settings, api: BatchV1Api, namespace: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        response = api.list_namespaced_cron_job(namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to list cronjobs in namespace '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error listing cronjobs in '{namespace}': {exc}"
        ) from exc

    items = []
    for c in response.items:
        containers = c.spec.job_template.spec.template.spec.containers or []
        active_jobs = [j.name for j in (c.status.active or [])]
        items.append({
            "name": c.metadata.name,
            "namespace": c.metadata.namespace,
            "schedule": c.spec.schedule,
            "suspend": c.spec.suspend or False,
            "active_jobs": active_jobs,
            "active_count": len(active_jobs),
            "last_schedule_time": c.status.last_schedule_time.isoformat()
            if c.status.last_schedule_time else None,
            "last_successful_time": c.status.last_successful_time.isoformat()
            if c.status.last_successful_time else None,
            "image": containers[0].image if containers else None,
            "labels": c.metadata.labels,
            "created_at": c.metadata.creation_timestamp.isoformat()
            if c.metadata.creation_timestamp else None,
        })
    return {"namespace": namespace, "cronjob_count": len(items), "cronjobs": items}


def describe_cronjob(
    settings: Settings, api: BatchV1Api, namespace: str, name: str
) -> dict[str, Any]:
    _ensure_namespace_allowed(settings, namespace)
    try:
        c = api.read_namespaced_cron_job(name=name, namespace=namespace)
    except ApiException as exc:
        raise KubernetesOperationsError(
            f"Failed to describe cronjob '{name}' in '{namespace}': {exc.reason}"
        ) from exc
    except Exception as exc:
        raise KubernetesOperationsError(
            f"Unexpected error describing cronjob '{name}': {exc}"
        ) from exc

    active_jobs = [
        {"name": j.name, "namespace": j.namespace}
        for j in (c.status.active or [])
    ]

    job_spec = c.spec.job_template.spec
    containers = job_spec.template.spec.containers if job_spec.template else []

    return {
        "name": c.metadata.name,
        "namespace": c.metadata.namespace,
        "labels": c.metadata.labels,
        "annotations": c.metadata.annotations,
        "created_at": c.metadata.creation_timestamp.isoformat()
        if c.metadata.creation_timestamp else None,
        "schedule": c.spec.schedule,
        "timezone": c.spec.time_zone,
        "suspend": c.spec.suspend or False,
        "concurrency_policy": c.spec.concurrency_policy,
        "starting_deadline_seconds": c.spec.starting_deadline_seconds,
        "successful_jobs_history_limit": c.spec.successful_jobs_history_limit,
        "failed_jobs_history_limit": c.spec.failed_jobs_history_limit,
        "last_schedule_time": c.status.last_schedule_time.isoformat()
        if c.status.last_schedule_time else None,
        "last_successful_time": c.status.last_successful_time.isoformat()
        if c.status.last_successful_time else None,
        "active_jobs": active_jobs,
        "job_completions": job_spec.completions,
        "job_parallelism": job_spec.parallelism,
        "job_backoff_limit": job_spec.backoff_limit,
        "container_specs": _container_specs(containers),
        "init_container_specs": _container_specs(
            job_spec.template.spec.init_containers if job_spec.template else []
        ),
    }
