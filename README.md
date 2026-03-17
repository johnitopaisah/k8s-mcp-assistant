# k8s-mcp-assistant

A read-only Kubernetes MCP (Model Context Protocol) server in Python that gives AI assistants full cluster inspection capabilities — pods, workloads, networking, storage, RBAC, events and more.

---

## Features

- **23 MCP tools** covering all major Kubernetes read operations
- **Read-only by default** — no mutations, ever
- **Namespace-restricted** or **cluster-wide** access via configuration
- **Multi-cluster support** via kubeconfig context switching
- **In-cluster support** — runs inside a pod using ServiceAccount credentials
- **Fully typed** with Pydantic response models
- **Tested** with pytest and unittest.mock — no live cluster required

---

## Supported tools

### Cluster-wide (no namespace required)
| Tool | Description |
|---|---|
| `health_check` | Server status, read-only mode and allowed namespaces |
| `list_namespaces_tool` | All namespaces with status, labels and creation time |
| `list_nodes_tool` | All nodes with roles, ready status, capacity, allocatable resources and taints |
| `describe_node_tool` | Full node detail — conditions, addresses, system info, capacity, events |
| `get_cluster_info_tool` | Server version, platform, Go version, build date |
| `list_api_resources_tool` | All API resource types across every group — kind, scope, verbs, short names |

### Pods
| Tool | Description |
|---|---|
| `list_pods_tool` | Pods in a namespace — status, node, restart count, ready ratio |
| `describe_pod_tool` | Full pod detail — conditions, container statuses, resources, events |
| `get_pod_logs_tool` | Pod logs with multi-container support and tail line control |

### Deployments
| Tool | Description |
|---|---|
| `list_deployments_tool` | Deployments with replica counts and image |
| `describe_deployment_tool` | Full deployment detail — replicas, strategy, container specs, conditions |

### StatefulSets
| Tool | Description |
|---|---|
| `list_statefulsets_tool` | StatefulSets with replica counts and service name |
| `describe_statefulset_tool` | Full detail — pod management policy, update strategy, volume claim templates |

### DaemonSets
| Tool | Description |
|---|---|
| `list_daemonsets_tool` | DaemonSets with desired/current/ready/available node counts |
| `describe_daemonset_tool` | Full detail — update strategy, node selector, tolerations |

### ReplicaSets
| Tool | Description |
|---|---|
| `list_replicasets_tool` | ReplicaSets with replica counts and owner references |
| `describe_replicaset_tool` | Full detail — selector, owner references, container specs |

### Jobs
| Tool | Description |
|---|---|
| `list_jobs_tool` | Jobs with completion status, active/succeeded/failed counts |
| `describe_job_tool` | Full detail — completions, parallelism, backoff limit, TTL, conditions |

### CronJobs
| Tool | Description |
|---|---|
| `list_cronjobs_tool` | CronJobs with schedule, suspend status, active count, last schedule time |
| `describe_cronjob_tool` | Full detail — timezone, concurrency policy, history limits, job spec |

### Services & Events
| Tool | Description |
|---|---|
| `list_services_tool` | Services with type, cluster IP, external IP and port mappings |
| `list_events_tool` | Namespace events sorted newest first, optionally filtered by object name |

---

## Project structure

```text
k8s-mcp-assistant/
├── .env                        # Local environment configuration (gitignored)
├── .env.example                # Environment variable reference
├── pyproject.toml              # Project metadata, dependencies, tool config
├── README.md
└── src/
    └── k8s_mcp_assistant/
        ├── __init__.py
        ├── config.py           # Settings loaded from environment variables
        ├── models.py           # Pydantic response models
        ├── server.py           # MCP server — all tool definitions
        └── kubernetes/
            ├── __init__.py
            ├── client.py       # Kubernetes API client initialisation and caching
            ├── cluster.py      # Cluster-wide: namespaces, nodes, version, API resources
            ├── deployments.py  # Deployment list and describe
            ├── events.py       # Namespace event listing
            ├── pods.py         # Pod list, describe, logs
            ├── services.py     # Service listing
            └── workloads.py    # StatefulSet, DaemonSet, ReplicaSet, Job, CronJob
tests/
    ├── test_cluster.py         # Cluster-wide tool tests
    ├── test_config.py          # Settings and namespace access tests
    ├── test_deployments.py     # Deployment tests
    ├── test_events.py          # Event tests
    ├── test_pods.py            # Pod tests
    ├── test_services.py        # Service tests
    └── test_workloads.py       # Workload tests (StatefulSet, DaemonSet, etc.)
```

---

## Installation

### Requirements

- Python 3.11+
- A kubeconfig file (`~/.kube/config`) or in-cluster ServiceAccount

### Local development

```bash
git clone https://github.com/your-org/k8s-mcp-assistant.git
cd k8s-mcp-assistant
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run the server

```bash
k8s-mcp-assistant
```

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `K8S_ALLOWED_NAMESPACES` | `""` (all) | Comma-separated list of allowed namespaces. Empty = allow all. |
| `K8S_READ_ONLY` | `true` | Read-only mode. Always keep `true`. |
| `KUBECONFIG` | `""` | Path to kubeconfig file (falls back to `~/.kube/config`). |
| `KUBECONFIG_PATH` | `""` | Explicit kubeconfig file path. |
| `KUBE_CONTEXT` | `""` | Kubeconfig context to use. Empty = current context. |
| `K8S_DEFAULT_LOG_TAIL_LINES` | `100` | Default number of log lines returned. |
| `K8S_MAX_LOG_TAIL_LINES` | `1000` | Maximum allowed log lines per request. |

### Example: restrict to specific namespaces

```bash
K8S_ALLOWED_NAMESPACES=default,kube-system,production
```

### Example: target a specific kubeconfig context

```bash
KUBE_CONTEXT=minikube
```

---

## Claude Desktop setup

Add this to your `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "k8s-mcp-assistant": {
      "command": "/path/to/your/.venv/bin/k8s-mcp-assistant",
      "env": {
        "K8S_ALLOWED_NAMESPACES": "",
        "K8S_READ_ONLY": "true",
        "KUBECONFIG": "/Users/you/.kube/config",
        "KUBE_CONTEXT": ""
      }
    }
  }
}
```

Replace `/path/to/your/.venv/bin/k8s-mcp-assistant` with the output of:

```bash
which k8s-mcp-assistant
```

After saving, fully quit Claude Desktop (`Cmd+Q`) and reopen it.

---

## Running tests

No live cluster required — all tests use mocks.

```bash
# Run all tests
python -m pytest

# Run a specific module
python -m pytest tests/test_pods.py -v

# Run all with verbose output
python -m pytest -v
```

---

## How namespace access control works

When `K8S_ALLOWED_NAMESPACES` is empty, **all namespaces are accessible**. When it contains a comma-separated list, only those namespaces are allowed — any tool call against an unlisted namespace returns a `namespace_access_denied` error immediately, before any Kubernetes API call is made.

Cluster-scoped tools (`list_namespaces_tool`, `list_nodes_tool`, `describe_node_tool`, `get_cluster_info_tool`, `list_api_resources_tool`) are always available regardless of this setting since they do not operate on a specific namespace.

---

## Response format

Every tool returns a JSON string with a consistent envelope:

**Success:**
```json
{
  "ok": true,
  "data": { ... }
}
```

**Error:**
```json
{
  "ok": false,
  "error_type": "kubernetes_operations_error",
  "message": "Failed to list pods in namespace 'default': Not Found"
}
```

Error types: `namespace_access_denied`, `kubernetes_client_error`, `kubernetes_operations_error`, `internal_server_error`.

---

## Roadmap

The following read operations are planned for upcoming releases:

- **Networking** — Ingresses, Endpoints, NetworkPolicies, IngressClasses
- **Storage** — PersistentVolumes, PersistentVolumeClaims, StorageClasses
- **Configuration** — ConfigMaps, Secrets (metadata only, never values)
- **RBAC** — Roles, RoleBindings, ClusterRoles, ClusterRoleBindings, ServiceAccounts
- **Autoscaling** — HorizontalPodAutoscalers, VerticalPodAutoscalers
- **Policy** — PodDisruptionBudgets, ResourceQuotas, LimitRanges
- **CRDs** — CustomResourceDefinitions and generic custom resource listing
