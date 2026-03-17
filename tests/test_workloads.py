from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.workloads import (
    list_statefulsets, describe_statefulset,
    list_daemonsets, describe_daemonset,
    list_replicasets, describe_replicaset,
    list_jobs, describe_job,
    list_cronjobs, describe_cronjob,
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
    c.env = []
    return c


def _mock_meta(name: str, namespace: str = "default") -> MagicMock:
    m = MagicMock()
    m.name = name
    m.namespace = namespace
    m.labels = {"app": name}
    m.annotations = {}
    m.creation_timestamp.isoformat.return_value = "2026-01-01T00:00:00"
    m.owner_references = []
    return m


# ── StatefulSets ───────────────────────────────────────────────────────────────

class TestListStatefulSets:
    def _mock_sts(self, name: str = "my-sts") -> MagicMock:
        s = MagicMock()
        s.metadata = _mock_meta(name)
        s.spec.replicas = 3
        s.spec.service_name = "my-svc"
        s.spec.template.spec.containers = [_mock_container()]
        s.status.ready_replicas = 3
        s.status.current_replicas = 3
        s.status.updated_replicas = 3
        return s

    def test_returns_statefulset_list(self):
        api = MagicMock()
        api.list_namespaced_stateful_set.return_value.items = [self._mock_sts()]
        result = list_statefulsets(settings=_settings(), api=api, namespace="default")
        assert result["statefulset_count"] == 1
        assert result["statefulsets"][0]["name"] == "my-sts"
        assert result["statefulsets"][0]["service_name"] == "my-svc"

    def test_empty_namespace(self):
        api = MagicMock()
        api.list_namespaced_stateful_set.return_value.items = []
        result = list_statefulsets(settings=_settings(), api=api, namespace="default")
        assert result["statefulset_count"] == 0

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_statefulsets(settings=_settings(["kube-system"]), api=api, namespace="default")

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespaced_stateful_set.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_statefulsets(settings=_settings(), api=api, namespace="default")


class TestDescribeStatefulSet:
    def _mock_sts(self) -> MagicMock:
        s = MagicMock()
        s.metadata = _mock_meta("my-sts")
        s.spec.replicas = 3
        s.spec.service_name = "my-svc"
        s.spec.pod_management_policy = "OrderedReady"
        s.spec.update_strategy.type = "RollingUpdate"
        s.spec.selector.match_labels = {"app": "my-sts"}
        s.spec.template.spec.containers = [_mock_container()]
        s.spec.template.spec.init_containers = []
        s.spec.volume_claim_templates = []
        s.status.ready_replicas = 3
        s.status.current_replicas = 3
        s.status.updated_replicas = 3
        s.status.conditions = []
        return s

    def test_returns_full_detail(self):
        api = MagicMock()
        api.read_namespaced_stateful_set.return_value = self._mock_sts()
        result = describe_statefulset(settings=_settings(), api=api, namespace="default", name="my-sts")
        assert result["name"] == "my-sts"
        assert result["pod_management_policy"] == "OrderedReady"
        assert result["update_strategy"] == "RollingUpdate"
        assert len(result["container_specs"]) == 1

    def test_not_found_raises_operations_error(self):
        api = MagicMock()
        api.read_namespaced_stateful_set.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(KubernetesOperationsError):
            describe_statefulset(settings=_settings(), api=api, namespace="default", name="missing")


# ── DaemonSets ─────────────────────────────────────────────────────────────────

class TestListDaemonSets:
    def _mock_ds(self, name: str = "my-ds") -> MagicMock:
        d = MagicMock()
        d.metadata = _mock_meta(name)
        d.spec.template.spec.containers = [_mock_container()]
        d.status.desired_number_scheduled = 3
        d.status.current_number_scheduled = 3
        d.status.number_ready = 3
        d.status.number_available = 3
        d.status.number_misscheduled = 0
        return d

    def test_returns_daemonset_list(self):
        api = MagicMock()
        api.list_namespaced_daemon_set.return_value.items = [self._mock_ds()]
        result = list_daemonsets(settings=_settings(), api=api, namespace="kube-system")
        assert result["daemonset_count"] == 1
        assert result["daemonsets"][0]["desired"] == 3
        assert result["daemonsets"][0]["ready"] == 3

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_daemonsets(settings=_settings(["kube-system"]), api=api, namespace="default")

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespaced_daemon_set.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_daemonsets(settings=_settings(), api=api, namespace="default")


class TestDescribeDaemonSet:
    def _mock_ds(self) -> MagicMock:
        d = MagicMock()
        d.metadata = _mock_meta("my-ds")
        d.spec.update_strategy.type = "RollingUpdate"
        d.spec.selector.match_labels = {"app": "my-ds"}
        d.spec.template.spec.node_selector = {"disktype": "ssd"}
        d.spec.template.spec.tolerations = []
        d.spec.template.spec.containers = [_mock_container()]
        d.spec.template.spec.init_containers = []
        d.status.desired_number_scheduled = 3
        d.status.current_number_scheduled = 3
        d.status.number_ready = 3
        d.status.number_available = 3
        d.status.number_misscheduled = 0
        d.status.conditions = []
        return d

    def test_returns_full_detail(self):
        api = MagicMock()
        api.read_namespaced_daemon_set.return_value = self._mock_ds()
        result = describe_daemonset(settings=_settings(), api=api, namespace="default", name="my-ds")
        assert result["name"] == "my-ds"
        assert result["update_strategy"] == "RollingUpdate"
        assert result["node_selector"] == {"disktype": "ssd"}

    def test_not_found_raises_operations_error(self):
        api = MagicMock()
        api.read_namespaced_daemon_set.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(KubernetesOperationsError):
            describe_daemonset(settings=_settings(), api=api, namespace="default", name="missing")


# ── ReplicaSets ────────────────────────────────────────────────────────────────

class TestListReplicaSets:
    def _mock_rs(self, name: str = "my-rs") -> MagicMock:
        r = MagicMock()
        r.metadata = _mock_meta(name)
        r.metadata.owner_references = []
        r.spec.replicas = 2
        r.spec.template.spec.containers = [_mock_container()]
        r.status.ready_replicas = 2
        r.status.available_replicas = 2
        return r

    def test_returns_replicaset_list(self):
        api = MagicMock()
        api.list_namespaced_replica_set.return_value.items = [self._mock_rs()]
        result = list_replicasets(settings=_settings(), api=api, namespace="default")
        assert result["replicaset_count"] == 1
        assert result["replicasets"][0]["desired"] == 2

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_replicasets(settings=_settings(["kube-system"]), api=api, namespace="default")

    def test_owner_reference_included(self):
        api = MagicMock()
        rs = self._mock_rs()
        owner = MagicMock()
        owner.kind = "Deployment"
        owner.name = "my-deploy"
        owner.uid = "abc-123"
        rs.metadata.owner_references = [owner]
        api.list_namespaced_replica_set.return_value.items = [rs]
        result = list_replicasets(settings=_settings(), api=api, namespace="default")
        owners = result["replicasets"][0]["owner_references"]
        assert owners[0]["kind"] == "Deployment"
        assert owners[0]["name"] == "my-deploy"


class TestDescribeReplicaSet:
    def _mock_rs(self) -> MagicMock:
        r = MagicMock()
        r.metadata = _mock_meta("my-rs")
        r.metadata.owner_references = []
        r.spec.replicas = 2
        r.spec.selector.match_labels = {"app": "my-rs"}
        r.spec.template.spec.containers = [_mock_container()]
        r.status.ready_replicas = 2
        r.status.available_replicas = 2
        r.status.fully_labeled_replicas = 2
        r.status.conditions = []
        return r

    def test_returns_full_detail(self):
        api = MagicMock()
        api.read_namespaced_replica_set.return_value = self._mock_rs()
        result = describe_replicaset(settings=_settings(), api=api, namespace="default", name="my-rs")
        assert result["name"] == "my-rs"
        assert result["desired"] == 2
        assert len(result["container_specs"]) == 1

    def test_not_found_raises_operations_error(self):
        api = MagicMock()
        api.read_namespaced_replica_set.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(KubernetesOperationsError):
            describe_replicaset(settings=_settings(), api=api, namespace="default", name="missing")


# ── Jobs ───────────────────────────────────────────────────────────────────────

class TestListJobs:
    def _mock_job(self, name: str = "my-job", complete: bool = True) -> MagicMock:
        j = MagicMock()
        j.metadata = _mock_meta(name)
        j.metadata.owner_references = []
        j.spec.completions = 1
        j.spec.parallelism = 1
        j.spec.template.spec.containers = [_mock_container()]
        j.status.active = 0
        j.status.succeeded = 1 if complete else 0
        j.status.failed = 0
        j.status.start_time.isoformat.return_value = "2026-01-01T00:00:00"
        j.status.completion_time.isoformat.return_value = "2026-01-01T00:01:00"
        cond = MagicMock()
        cond.type = "Complete"
        cond.status = "True" if complete else "False"
        j.status.conditions = [cond]
        return j

    def test_returns_job_list(self):
        api = MagicMock()
        api.list_namespaced_job.return_value.items = [self._mock_job()]
        result = list_jobs(settings=_settings(), api=api, namespace="default")
        assert result["job_count"] == 1
        assert result["jobs"][0]["status"] == "Complete"
        assert result["jobs"][0]["succeeded"] == 1

    def test_running_job_status(self):
        api = MagicMock()
        j = self._mock_job(complete=False)
        j.status.active = 1
        j.status.conditions = []
        api.list_namespaced_job.return_value.items = [j]
        result = list_jobs(settings=_settings(), api=api, namespace="default")
        assert result["jobs"][0]["status"] == "Running"

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_jobs(settings=_settings(["kube-system"]), api=api, namespace="default")

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespaced_job.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_jobs(settings=_settings(), api=api, namespace="default")


class TestDescribeJob:
    def _mock_job(self) -> MagicMock:
        j = MagicMock()
        j.metadata = _mock_meta("my-job")
        j.metadata.owner_references = []
        j.spec.completions = 1
        j.spec.parallelism = 1
        j.spec.backoff_limit = 6
        j.spec.active_deadline_seconds = None
        j.spec.ttl_seconds_after_finished = 3600
        j.spec.selector.match_labels = {"job-name": "my-job"}
        j.spec.template.spec.containers = [_mock_container()]
        j.spec.template.spec.init_containers = []
        j.status.active = 0
        j.status.succeeded = 1
        j.status.failed = 0
        j.status.start_time.isoformat.return_value = "2026-01-01T00:00:00"
        j.status.completion_time.isoformat.return_value = "2026-01-01T00:01:00"
        j.status.conditions = []
        return j

    def test_returns_full_detail(self):
        api = MagicMock()
        api.read_namespaced_job.return_value = self._mock_job()
        result = describe_job(settings=_settings(), api=api, namespace="default", name="my-job")
        assert result["name"] == "my-job"
        assert result["backoff_limit"] == 6
        assert result["ttl_seconds_after_finished"] == 3600
        assert len(result["container_specs"]) == 1

    def test_not_found_raises_operations_error(self):
        api = MagicMock()
        api.read_namespaced_job.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(KubernetesOperationsError):
            describe_job(settings=_settings(), api=api, namespace="default", name="missing")


# ── CronJobs ───────────────────────────────────────────────────────────────────

class TestListCronJobs:
    def _mock_cj(self, name: str = "my-cron") -> MagicMock:
        c = MagicMock()
        c.metadata = _mock_meta(name)
        c.spec.schedule = "*/5 * * * *"
        c.spec.suspend = False
        c.spec.job_template.spec.template.spec.containers = [_mock_container()]
        c.status.active = []
        c.status.last_schedule_time.isoformat.return_value = "2026-01-01T00:00:00"
        c.status.last_successful_time.isoformat.return_value = "2026-01-01T00:00:00"
        return c

    def test_returns_cronjob_list(self):
        api = MagicMock()
        api.list_namespaced_cron_job.return_value.items = [self._mock_cj()]
        result = list_cronjobs(settings=_settings(), api=api, namespace="default")
        assert result["cronjob_count"] == 1
        assert result["cronjobs"][0]["schedule"] == "*/5 * * * *"
        assert result["cronjobs"][0]["suspend"] is False

    def test_empty_namespace(self):
        api = MagicMock()
        api.list_namespaced_cron_job.return_value.items = []
        result = list_cronjobs(settings=_settings(), api=api, namespace="default")
        assert result["cronjob_count"] == 0

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_cronjobs(settings=_settings(["kube-system"]), api=api, namespace="default")

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespaced_cron_job.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_cronjobs(settings=_settings(), api=api, namespace="default")


class TestDescribeCronJob:
    def _mock_cj(self) -> MagicMock:
        c = MagicMock()
        c.metadata = _mock_meta("my-cron")
        c.spec.schedule = "0 * * * *"
        c.spec.time_zone = "UTC"
        c.spec.suspend = False
        c.spec.concurrency_policy = "Allow"
        c.spec.starting_deadline_seconds = None
        c.spec.successful_jobs_history_limit = 3
        c.spec.failed_jobs_history_limit = 1
        c.spec.job_template.spec.completions = 1
        c.spec.job_template.spec.parallelism = 1
        c.spec.job_template.spec.backoff_limit = 3
        c.spec.job_template.spec.template.spec.containers = [_mock_container()]
        c.spec.job_template.spec.template.spec.init_containers = []
        c.status.active = []
        c.status.last_schedule_time.isoformat.return_value = "2026-01-01T00:00:00"
        c.status.last_successful_time.isoformat.return_value = "2026-01-01T00:00:00"
        return c

    def test_returns_full_detail(self):
        api = MagicMock()
        api.read_namespaced_cron_job.return_value = self._mock_cj()
        result = describe_cronjob(settings=_settings(), api=api, namespace="default", name="my-cron")
        assert result["name"] == "my-cron"
        assert result["schedule"] == "0 * * * *"
        assert result["concurrency_policy"] == "Allow"
        assert result["successful_jobs_history_limit"] == 3
        assert len(result["container_specs"]) == 1

    def test_not_found_raises_operations_error(self):
        api = MagicMock()
        api.read_namespaced_cron_job.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(KubernetesOperationsError):
            describe_cronjob(settings=_settings(), api=api, namespace="default", name="missing")
