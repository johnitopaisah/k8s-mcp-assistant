from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.cluster import (
    list_namespaces,
    list_nodes,
    describe_node,
    get_cluster_info,
    list_api_resources,
)
from k8s_mcp_assistant.kubernetes.pods import KubernetesOperationsError
from kubernetes.client.exceptions import ApiException


def _settings() -> Settings:
    return Settings(
        allowed_namespaces=[],
        read_only=True,
        kubeconfig_path=None,
        kubeconfig=None,
        kube_context=None,
        kube_api_server=None,
        kube_user=None,
        kube_cluster=None,
        default_log_tail_lines=100,
        max_log_tail_lines=1000,
    )


def _mock_namespace(name: str, phase: str = "Active") -> MagicMock:
    ns = MagicMock()
    ns.metadata.name = name
    ns.metadata.labels = {"kubernetes.io/metadata.name": name}
    ns.metadata.annotations = {}
    ns.metadata.creation_timestamp.isoformat.return_value = "2026-01-01T00:00:00"
    ns.status.phase = phase
    return ns


def _mock_node(name: str = "node-1", ready: str = "True") -> MagicMock:
    node = MagicMock()
    node.metadata.name = name
    node.metadata.labels = {"node-role.kubernetes.io/control-plane": ""}
    node.metadata.annotations = {}
    node.metadata.creation_timestamp.isoformat.return_value = "2026-01-01T00:00:00"
    node.spec.unschedulable = False
    node.spec.taints = []

    ready_condition = MagicMock()
    ready_condition.type = "Ready"
    ready_condition.status = ready
    ready_condition.reason = "KubeletReady"
    ready_condition.message = "kubelet is posting ready status"
    ready_condition.last_heartbeat_time.isoformat.return_value = "2026-01-01T00:01:00"
    ready_condition.last_transition_time.isoformat.return_value = "2026-01-01T00:00:00"
    node.status.conditions = [ready_condition]

    node.status.addresses = []
    node.status.capacity = {"cpu": "4", "memory": "8Gi"}
    node.status.allocatable = {"cpu": "3900m", "memory": "7Gi"}

    node_info = MagicMock()
    node_info.os_image = "Ubuntu 22.04"
    node_info.kernel_version = "5.15.0"
    node_info.operating_system = "linux"
    node_info.architecture = "amd64"
    node_info.container_runtime_version = "containerd://1.6.0"
    node_info.kubelet_version = "v1.29.0"
    node_info.kube_proxy_version = "v1.29.0"
    node.status.node_info = node_info
    return node


# ── list_namespaces ────────────────────────────────────────────────────────────

class TestListNamespaces:
    def test_returns_namespace_list(self):
        api = MagicMock()
        api.list_namespace.return_value.items = [
            _mock_namespace("default"),
            _mock_namespace("kube-system"),
        ]
        result = list_namespaces(settings=_settings(), api=api)
        assert result["namespace_count"] == 2
        names = [n["name"] for n in result["namespaces"]]
        assert "default" in names
        assert "kube-system" in names

    def test_empty_cluster(self):
        api = MagicMock()
        api.list_namespace.return_value.items = []
        result = list_namespaces(settings=_settings(), api=api)
        assert result["namespace_count"] == 0
        assert result["namespaces"] == []

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespace.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_namespaces(settings=_settings(), api=api)

    def test_namespace_fields_present(self):
        api = MagicMock()
        api.list_namespace.return_value.items = [_mock_namespace("staging", "Active")]
        result = list_namespaces(settings=_settings(), api=api)
        ns = result["namespaces"][0]
        assert ns["name"] == "staging"
        assert ns["status"] == "Active"
        assert "labels" in ns
        assert "created_at" in ns


# ── list_nodes ─────────────────────────────────────────────────────────────────

class TestListNodes:
    def test_returns_node_list(self):
        api = MagicMock()
        api.list_node.return_value.items = [_mock_node("minikube")]
        result = list_nodes(settings=_settings(), api=api)
        assert result["node_count"] == 1
        assert result["nodes"][0]["name"] == "minikube"

    def test_roles_extracted_from_labels(self):
        api = MagicMock()
        node = _mock_node()
        node.metadata.labels = {
            "node-role.kubernetes.io/control-plane": "",
            "node-role.kubernetes.io/master": "",
        }
        api.list_node.return_value.items = [node]
        result = list_nodes(settings=_settings(), api=api)
        roles = result["nodes"][0]["roles"]
        assert "control-plane" in roles
        assert "master" in roles

    def test_worker_role_default_when_no_role_labels(self):
        api = MagicMock()
        node = _mock_node()
        node.metadata.labels = {"kubernetes.io/hostname": "worker-1"}
        api.list_node.return_value.items = [node]
        result = list_nodes(settings=_settings(), api=api)
        assert result["nodes"][0]["roles"] == ["worker"]

    def test_ready_status_extracted(self):
        api = MagicMock()
        api.list_node.return_value.items = [_mock_node(ready="True")]
        result = list_nodes(settings=_settings(), api=api)
        assert result["nodes"][0]["ready"] == "True"

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_node.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_nodes(settings=_settings(), api=api)

    def test_capacity_and_allocatable_present(self):
        api = MagicMock()
        api.list_node.return_value.items = [_mock_node()]
        result = list_nodes(settings=_settings(), api=api)
        node = result["nodes"][0]
        assert "cpu" in node["capacity"]
        assert "cpu" in node["allocatable"]


# ── describe_node ──────────────────────────────────────────────────────────────

class TestDescribeNode:
    def test_returns_full_node_detail(self):
        api = MagicMock()
        api.read_node.return_value = _mock_node("minikube")
        api.list_event_for_all_namespaces.return_value.items = []
        result = describe_node(settings=_settings(), api=api, node_name="minikube")
        assert result["name"] == "minikube"
        assert "conditions" in result
        assert "system_info" in result
        assert "capacity" in result
        assert "allocatable" in result
        assert "addresses" in result

    def test_node_not_found_raises_operations_error(self):
        api = MagicMock()
        api.read_node.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(KubernetesOperationsError):
            describe_node(settings=_settings(), api=api, node_name="ghost-node")

    def test_events_failure_does_not_raise(self):
        api = MagicMock()
        api.read_node.return_value = _mock_node()
        api.list_event_for_all_namespaces.side_effect = Exception("events down")
        result = describe_node(settings=_settings(), api=api, node_name="node-1")
        assert result["events"] == []

    def test_system_info_populated(self):
        api = MagicMock()
        api.read_node.return_value = _mock_node()
        api.list_event_for_all_namespaces.return_value.items = []
        result = describe_node(settings=_settings(), api=api, node_name="node-1")
        info = result["system_info"]
        assert info["os_image"] == "Ubuntu 22.04"
        assert info["kubelet_version"] == "v1.29.0"
        assert info["architecture"] == "amd64"

    def test_roles_extracted_correctly(self):
        api = MagicMock()
        node = _mock_node()
        node.metadata.labels = {"node-role.kubernetes.io/control-plane": ""}
        api.read_node.return_value = node
        api.list_event_for_all_namespaces.return_value.items = []
        result = describe_node(settings=_settings(), api=api, node_name="node-1")
        assert "control-plane" in result["roles"]


# ── get_cluster_info ───────────────────────────────────────────────────────────

class TestGetClusterInfo:
    def test_returns_version_info(self):
        version_api = MagicMock()
        version_api.get_code.return_value = MagicMock(
            git_version="v1.29.0",
            major="1",
            minor="29",
            platform="linux/amd64",
            go_version="go1.21.0",
            build_date="2024-01-01T00:00:00Z",
            compiler="gc",
        )
        result = get_cluster_info(settings=_settings(), version_api=version_api)
        assert result["git_version"] == "v1.29.0"
        assert result["major"] == "1"
        assert result["minor"] == "29"
        assert result["platform"] == "linux/amd64"

    def test_api_exception_raises_operations_error(self):
        version_api = MagicMock()
        version_api.get_code.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            get_cluster_info(settings=_settings(), version_api=version_api)

    def test_all_fields_present(self):
        version_api = MagicMock()
        version_api.get_code.return_value = MagicMock(
            git_version="v1.28.5",
            major="1",
            minor="28",
            platform="linux/arm64",
            go_version="go1.20.0",
            build_date="2023-11-01T00:00:00Z",
            compiler="gc",
        )
        result = get_cluster_info(settings=_settings(), version_api=version_api)
        for field in ["git_version", "major", "minor", "platform", "go_version", "build_date", "compiler"]:
            assert field in result


# ── list_api_resources ─────────────────────────────────────────────────────────

class TestListApiResources:
    def test_returns_resource_list(self):
        api_client = MagicMock()
        with (
            patch("k8s_mcp_assistant.kubernetes.cluster.k8s_client.CoreV1Api") as mock_core,
            patch("k8s_mcp_assistant.kubernetes.cluster.k8s_client.ApisApi") as mock_apis,
        ):
            pod_resource = MagicMock()
            pod_resource.name = "pods"
            pod_resource.kind = "Pod"
            pod_resource.namespaced = True
            pod_resource.verbs = ["get", "list", "watch"]
            pod_resource.short_names = ["po"]

            mock_core.return_value.get_api_resources.return_value.resources = [pod_resource]
            mock_apis.return_value.get_api_versions.return_value.groups = []

            result = list_api_resources(settings=_settings(), api_client=api_client)
            assert result["resource_count"] >= 1
            kinds = [r["kind"] for r in result["resources"]]
            assert "Pod" in kinds

    def test_subresources_excluded(self):
        api_client = MagicMock()
        with (
            patch("k8s_mcp_assistant.kubernetes.cluster.k8s_client.CoreV1Api") as mock_core,
            patch("k8s_mcp_assistant.kubernetes.cluster.k8s_client.ApisApi") as mock_apis,
        ):
            log_resource = MagicMock()
            log_resource.name = "pods/log"
            log_resource.kind = "Pod"
            log_resource.namespaced = True
            log_resource.verbs = ["get"]
            log_resource.short_names = []

            mock_core.return_value.get_api_resources.return_value.resources = [log_resource]
            mock_apis.return_value.get_api_versions.return_value.groups = []

            result = list_api_resources(settings=_settings(), api_client=api_client)
            # pods/log subresource must not appear
            names = [r["name"] for r in result["resources"]]
            assert "pods/log" not in names

    def test_core_api_failure_returns_partial(self):
        api_client = MagicMock()
        with (
            patch("k8s_mcp_assistant.kubernetes.cluster.k8s_client.CoreV1Api") as mock_core,
            patch("k8s_mcp_assistant.kubernetes.cluster.k8s_client.ApisApi") as mock_apis,
        ):
            mock_core.return_value.get_api_resources.side_effect = Exception("API down")
            mock_apis.return_value.get_api_versions.return_value.groups = []
            # Should not raise — returns empty gracefully
            result = list_api_resources(settings=_settings(), api_client=api_client)
            assert "resource_count" in result
            assert "resources" in result
