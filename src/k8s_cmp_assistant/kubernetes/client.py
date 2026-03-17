from __future__ import annotations

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from k8s_cmp_assistant.config import Settings

class KubernetesClientError(Exception):
    """Raised when Kubernetes client initialization fails."""

class KubernetesClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_client = self._initialize_client()

    def _initialize_client(self) -> client.ApiClient:
        try:
            if self.settings.kubeconfig:
                config.load_kube_config_from_dict(
                    {
                        "apiVersion": "v1",
                        "clusters": [
                            {
                                "cluster": {
                                    "server": self.settings.kube_api_server,
                                    "certificate-authority-data": self.settings.kube_cluster,
                                },
                                "name": "cluster",
                            }
                        ],
                        "contexts": [
                            {
                                "context": {
                                    "cluster": "cluster",
                                    "user": "user",
                                },
                                "name": "context",
                            }
                        ],
                        "current-context": "context",
                        "kind": "Config",
                        "users": [
                            {
                                "name": "user",
                                "user": {
                                    "token": self.settings.kube_user,
                                },
                            }
                        ],
                    }
                )
            elif self.settings.kubeconfig_path:
                config.load_kube_config(config_file=self.settings.kubeconfig_path)
            else:
                config.load_kube_config()
            return client.ApiClient()
        except ConfigException as e:
            raise KubernetesClientError(f"Failed to initialize Kubernetes client: {e}")

def load_kube_configuration(settings: Settings) -> None:
    """
    Load Kubernetes configuration with the following preference:
    1. Explicit kubeconfig path/context from settings
    2. default kubeconfig file (e.g., ~/.kube/config)
    3. in-cluster configuration (if running inside a Kubernetes cluster)
    """
    try:
        if settings.kubeconfig or settings.kube_context:
            config.load_kube_config(
                config_file=settings.kubeconfig_path,
                context=settings.kube_context,
            )
            return
        
        try:
            config.load_kube_config()
            return
        except ConfigException:
            config.load_incluster_config()
    except Exception as exc:
        raise KubernetesClientError(
            "Failed to load Kubernetes configuration: "
            "Check your kubeconfig, context, and in-cluster configuration settings."
        ) from exc

def get_core_v1_api(settings: Settings) -> client.CoreV1Api:
    load_kube_configuration(settings)
    return client.CoreV1Api()

def get_apps_v1_api(settings: Settings) -> client.AppsV1Api:
    load_kube_configuration(settings)
    return client.AppsV1Api()