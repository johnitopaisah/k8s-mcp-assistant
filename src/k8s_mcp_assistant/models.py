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


# ── Cluster-wide models ────────────────────────────────────────────────────────

class NamespaceSummary(BaseModel):
    name: str
    status: Optional[str] = None
    labels: Optional[dict[str, str]] = None
    annotations: Optional[dict[str, str]] = None
    created_at: Optional[str] = None


class NamespaceList(BaseModel):
    namespace_count: int
    namespaces: list[NamespaceSummary]


class NodeTaint(BaseModel):
    key: str
    effect: str
    value: Optional[str] = None


class NodeSummary(BaseModel):
    name: str
    roles: list[str]
    ready: str
    kubelet_version: Optional[str] = None
    os_image: Optional[str] = None
    container_runtime: Optional[str] = None
    capacity: dict[str, str] = {}
    allocatable: dict[str, str] = {}
    taints: list[NodeTaint] = []
    unschedulable: bool = False
    created_at: Optional[str] = None


class NodeList(BaseModel):
    node_count: int
    nodes: list[NodeSummary]


class NodeCondition(BaseModel):
    type: str
    status: str
    reason: Optional[str] = None
    message: Optional[str] = None
    last_heartbeat_time: Optional[str] = None
    last_transition_time: Optional[str] = None


class NodeSystemInfo(BaseModel):
    os_image: Optional[str] = None
    kernel_version: Optional[str] = None
    os: Optional[str] = None
    architecture: Optional[str] = None
    container_runtime: Optional[str] = None
    kubelet_version: Optional[str] = None
    kube_proxy_version: Optional[str] = None


class NodeDetail(BaseModel):
    name: str
    roles: list[str]
    labels: Optional[dict[str, str]] = None
    annotations: Optional[dict[str, str]] = None
    created_at: Optional[str] = None
    unschedulable: bool = False
    taints: list[NodeTaint] = []
    conditions: list[NodeCondition] = []
    addresses: list[dict[str, str]] = []
    capacity: dict[str, str] = {}
    allocatable: dict[str, str] = {}
    system_info: NodeSystemInfo = NodeSystemInfo()
    events: list[EventSummary] = []


class ClusterInfo(BaseModel):
    git_version: Optional[str] = None
    major: Optional[str] = None
    minor: Optional[str] = None
    platform: Optional[str] = None
    go_version: Optional[str] = None
    build_date: Optional[str] = None
    compiler: Optional[str] = None


class ApiResource(BaseModel):
    name: str
    kind: str
    namespaced: bool
    group: str
    version: str
    verbs: list[str] = []
    short_names: list[str] = []


class ApiResourceList(BaseModel):
    resource_count: int
    resources: list[ApiResource]


# Allow forward references
PodDetail.model_rebuild()
