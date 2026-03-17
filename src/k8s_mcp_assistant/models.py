from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


# ── Container models ───────────────────────────────────────────────────────────

class ContainerPort(BaseModel):
    name: Optional[str] = None
    container_port: int
    protocol: str


class ContainerResources(BaseModel):
    requests: dict[str, str] = {}
    limits: dict[str, str] = {}


class ContainerSpec(BaseModel):
    name: str
    image: str
    resources: ContainerResources = ContainerResources()
    ports: list[ContainerPort] = []


class ContainerState(BaseModel):
    running: Optional[dict[str, Any]] = None
    waiting: Optional[dict[str, Any]] = None
    terminated: Optional[dict[str, Any]] = None


class ContainerStatus(BaseModel):
    name: str
    ready: bool
    restart_count: int
    image: str
    state: ContainerState = ContainerState()


# ── Pod models ─────────────────────────────────────────────────────────────────

class PodCondition(BaseModel):
    type: str
    status: str
    reason: Optional[str] = None
    message: Optional[str] = None
    last_transition_time: Optional[str] = None


class PodSummary(BaseModel):
    name: str
    namespace: str
    status: Optional[str] = None
    node: Optional[str] = None
    restart_count: int = 0
    started_at: Optional[str] = None
    labels: Optional[dict[str, str]] = None
    ip: Optional[str] = None
    created_at: Optional[str] = None
    ready_containers: str
    containers: list[str]


class PodList(BaseModel):
    namespace: str
    pod_count: int
    pods: list[PodSummary]


class PodDetail(BaseModel):
    name: str
    namespace: str
    node: Optional[str] = None
    status: Optional[str] = None
    pod_ip: Optional[str] = None
    host_ip: Optional[str] = None
    created_at: Optional[str] = None
    labels: Optional[dict[str, str]] = None
    annotations: Optional[dict[str, str]] = None
    conditions: list[PodCondition] = []
    container_specs: list[ContainerSpec] = []
    container_statuses: list[ContainerStatus] = []
    events: list["EventSummary"] = []


class PodLogs(BaseModel):
    pod_name: str
    namespace: str
    container: Optional[str] = None
    logs: str


# ── Deployment models ──────────────────────────────────────────────────────────

class DeploymentSummary(BaseModel):
    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int
    image: Optional[str] = None
    created_at: Optional[str] = None
    labels: Optional[dict[str, str]] = None


class DeploymentList(BaseModel):
    namespace: str
    deployment_count: int
    deployments: list[DeploymentSummary]


# ── Service models ─────────────────────────────────────────────────────────────

class ServicePort(BaseModel):
    name: Optional[str] = None
    port: int
    target_port: Optional[str] = None
    protocol: str
    node_port: Optional[int] = None


class ServiceSummary(BaseModel):
    name: str
    namespace: str
    type: str
    cluster_ip: Optional[str] = None
    external_ip: Optional[str] = None
    ports: list[ServicePort] = []
    selector: Optional[dict[str, str]] = None
    created_at: Optional[str] = None


class ServiceList(BaseModel):
    namespace: str
    service_count: int
    services: list[ServiceSummary]


# ── Event models ───────────────────────────────────────────────────────────────

class EventSummary(BaseModel):
    type: str
    reason: str
    message: str
    count: Optional[int] = None
    first_time: Optional[str] = None
    last_time: Optional[str] = None
    source: Optional[str] = None
    involved_object: Optional[str] = None


class EventList(BaseModel):
    namespace: str
    event_count: int
    events: list[EventSummary]


# Allow forward references (PodDetail references EventSummary)
PodDetail.model_rebuild()
