from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.deployments import (
    list_deployments,
    describe_deployment,
)
from k8s_mcp_assistant.kubernetes.pods import (
    KubernetesOperationsError,
    NamespaceAccessError,
)
from kubernetes.client.exceptions import ApiException


def _settings(allowed: list[str] | None = None) -> Settings:
    return Settings(
        allowed_namespaces=allowed or [],
        read_only=True,
        kubeconfig_path=None, kubeconfig=None, kube_context=None,
        kube_api_server=None, kube_user=None, kube_cluster=None,
        default_log_tail_lines=100, max_log_tail_lines=1000,
    )


def _mock_container(name: str = "app", image: str = "nginx:latest") -> MagicMock:
    c = MagicMock()
    c.name = name
    c.image = image
    c.resources.requests = {"cpu": "100m", "memory": "128Mi"}
    c.resources.limits = {"memory": "256Mi"}
    c.ports = []
    return c


def _mock_deployment(name: str = "my-deploy", namespace: str = "default") -> MagicMock:
    d = MagicMock()
    d.metadata.name = name
    d.metadata.namespace = namespace
    d.metadata.labels = {"app": name}
    d.metadata.annotations = {}
    d.metadata.creation_timestamp.isoformat.return_value = "2026-01-01T00:00:00"
    d.spec.replicas = 3
    d.spec.strategy.type = "RollingUpdate"
    d.spec.selector.match_labels = {"app": name}
    d.spec.template.spec.containers = [_mock_container()]
    d.status.ready_replicas = 3
    d.status.available_replicas = 3
    d.status.updated_replicas = 3
    d.status.conditions = []
    return d


class TestListDeployments:
    def test_returns_deployment_list(self):
        api = MagicMock()
        api.list_namespaced_deployment.return_value.items = [_mock_deployment()]
        result = list_deployments(settings=_settings(), api=api, namespace="default")
        assert result["namespace"] == "default"
        assert result["deployment_count"] == 1
        assert result["deployments"][0]["name"] == "my-deploy"

    def test_replica_counts_correct(self):
        api = MagicMock()
        api.list_namespaced_deployment.return_value.items = [_mock_deployment()]
        result = list_deployments(settings=_settings(), api=api, namespace="default")
        dep = result["deployments"][0]
        assert dep["replicas"] == 3
        assert dep["ready_replicas"] == 3
        assert dep["available_replicas"] == 3

    def test_image_from_first_container(self):
        api = MagicMock()
        api.list_namespaced_deployment.return_value.items = [_mock_deployment()]
        result = list_deployments(settings=_settings(), api=api, namespace="default")
        assert result["deployments"][0]["image"] == "nginx:latest"

    def test_empty_namespace_returns_empty_list(self):
        api = MagicMock()
        api.list_namespaced_deployment.return_value.items = []
        result = list_deployments(settings=_settings(), api=api, namespace="default")
        assert result["deployment_count"] == 0
        assert result["deployments"] == []

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_deployments(settings=_settings(["kube-system"]), api=api, namespace="default")

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespaced_deployment.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_deployments(settings=_settings(), api=api, namespace="default")

    def test_no_containers_image_is_none(self):
        api = MagicMock()
        dep = _mock_deployment()
        dep.spec.template.spec.containers = []
        api.list_namespaced_deployment.return_value.items = [dep]
        result = list_deployments(settings=_settings(), api=api, namespace="default")
        assert result["deployments"][0]["image"] is None


class TestDescribeDeployment:
    def test_returns_full_detail(self):
        api = MagicMock()
        api.read_namespaced_deployment.return_value = _mock_deployment()
        result = describe_deployment(
            settings=_settings(), api=api, namespace="default", deployment_name="my-deploy"
        )
        assert result["name"] == "my-deploy"
        assert result["strategy"] == "RollingUpdate"
        assert result["replicas"] == 3
        assert len(result["container_specs"]) == 1

    def test_selector_present(self):
        api = MagicMock()
        api.read_namespaced_deployment.return_value = _mock_deployment()
        result = describe_deployment(
            settings=_settings(), api=api, namespace="default", deployment_name="my-deploy"
        )
        assert result["selector"] == {"app": "my-deploy"}

    def test_conditions_included(self):
        api = MagicMock()
        dep = _mock_deployment()
        cond = MagicMock()
        cond.type = "Available"
        cond.status = "True"
        cond.reason = "MinimumReplicasAvailable"
        cond.message = "Deployment has minimum availability."
        cond.last_update_time.isoformat.return_value = "2026-01-01T00:00:00"
        dep.status.conditions = [cond]
        api.read_namespaced_deployment.return_value = dep
        result = describe_deployment(
            settings=_settings(), api=api, namespace="default", deployment_name="my-deploy"
        )
        assert len(result["conditions"]) == 1
        assert result["conditions"][0]["type"] == "Available"

    def test_not_found_raises_operations_error(self):
        api = MagicMock()
        api.read_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(KubernetesOperationsError):
            describe_deployment(
                settings=_settings(), api=api, namespace="default", deployment_name="missing"
            )

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            describe_deployment(
                settings=_settings(["kube-system"]), api=api,
                namespace="default", deployment_name="my-deploy"
            )

    def test_container_resources_included(self):
        api = MagicMock()
        api.read_namespaced_deployment.return_value = _mock_deployment()
        result = describe_deployment(
            settings=_settings(), api=api, namespace="default", deployment_name="my-deploy"
        )
        spec = result["container_specs"][0]
        assert spec["name"] == "app"
        assert spec["image"] == "nginx:latest"
        assert "requests" in spec["resources"]
        assert "limits" in spec["resources"]
