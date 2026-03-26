# Plan: Infrastructure Monitoring Page

**Status:** Draft
**Created:** 2026-02-25
**Owns (source of truth):** Infrastructure monitoring feature (ERP)
**Touches:** Backend (eva_platform module), Frontend (new page + components), env config

---

## Context

We need a new page in the Eva ERP to monitor OpenClaw infrastructure — Hetzner hosts, employee allocations, Docker containers, and agent workspaces. This gives operators full visibility into the runtime without needing to SSH manually.

**Current state:** The ERP has a `/monitoring` page for service health checks but no infrastructure visibility. All OpenClaw infrastructure data lives in the Eva production DB (accessible via `EVA_DATABASE_URL`). Hosts are Hetzner CX53 servers managed by the autoscaler.

**Goal:** A single page where operators can see all hosts, their employees, Docker container status, agent configuration, workspace files, and container logs.

---

## Design Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Page URL | `/infrastructure` | Consistent with `/monitoring` naming |
| Page title | "Infrastructure" | Subtitle: "OpenClaw runtime hosts and employees" |
| Sidebar location | "Eva Platform" group, below "Monitoring" | Logical grouping |
| Layout | Two-panel + detail sheet | Server cards (left), employee list (right), slide-over detail |
| Data source (DB) | Eva production DB via `EVA_DATABASE_URL` | Read-only, existing pattern |
| SSH library | `asyncssh` (v2.22.0) | Native async, built-in SFTP, SSH multiplexing |
| File browsing | Full filesystem, default `/root/.openclaw/` | SFTP for browsing, no shell parsing |
| Container logs | Yes, last 100 lines | Terminal-style panel in detail sheet |
| Host metrics | DB-only (Phase 1) | Occupancy, state, heartbeat — no Hetzner API |
| Access control | All ERP users | ERP is already an internal admin tool |
| Actions scope | Read-only (Phase 1) | No restart/redeploy — Phase 2 addition |
| Env vars needed | `EVA_SSH_PRIVATE_KEY_BASE64`, `HETZNER_API_TOKEN` | SSH key for host access, Hetzner token for future use |

---

## Architecture

```
ERP Frontend ──→ ERP Backend ──→ Eva Production DB (hosts, allocations, agents, events)
                     │
                     └──→ SSH (asyncssh) ──→ Hetzner Host VPS
                              ├── docker ps/inspect/logs (container status)
                              └── SFTP (file browsing)
```

### Data Layers

| Layer | Source | Data | Latency |
|-------|--------|------|---------|
| DB | Eva production DB | Hosts, allocations, agents, events | ~50ms |
| SSH/Docker | asyncssh → host | Container status, logs | ~1-3s |
| SSH/SFTP | asyncssh → host | File listing, file content | ~1-2s |

---

## Implementation Steps

### Step 1: Backend — Mirror Models

**File:** `backend/src/eva_platform/models.py`

Add OpenClaw mirror models (extend `EvaBase`, read-only from Eva production DB):

```python
class EvaOpenclawRuntimeHost(EvaBase):
    __tablename__ = "openclaw_runtime_hosts"
    id: UUID
    provider_host_id: str
    name: str
    region: str           # default "nbg1"
    host_class: str       # "cx53"
    state: str            # active|draining|offline|released
    public_ip: str
    vcpu: int
    ram_mb: int
    disk_gb: int
    max_tenants: int
    saturation: float
    last_heartbeat_at: DateTime

class EvaOpenclawRuntimeAllocation(EvaBase):
    __tablename__ = "openclaw_runtime_allocations"
    id: UUID
    openclaw_agent_id: UUID
    runtime_host_id: UUID
    state: str            # queued|placed|running|recovering|error|released
    tenant_class: str
    cpu_reservation_mcpu: int
    ram_reservation_mb: int
    gateway_port: int
    container_name: str
    queued_reason: str
    reconnect_risk: str
    placed_at: DateTime
    started_at: DateTime

class EvaOpenclawAgent(EvaBase):
    __tablename__ = "openclaw_agents"
    id: UUID
    agent_id: UUID
    account_id: UUID
    label: str
    status: str           # draft|provisioning|active|error...
    status_detail: str
    error: str
    phone_number: str
    vps_ip: str
    connections_state: dict  # JSONB — channel states
    selected_channels: list  # channel list if exists
    whatsapp_connected: bool
    telegram_connected: bool
    provisioning_started_at: DateTime
    provisioning_completed_at: DateTime

class EvaOpenclawRuntimeEvent(EvaBase):
    __tablename__ = "openclaw_runtime_events"
    id: UUID
    source: str
    event_type: str
    severity: str
    reason_code: str
    payload: dict         # JSONB
    openclaw_agent_id: UUID
    runtime_host_id: UUID
    created_at: DateTime
```

- [ ] Add models to `models.py`

---

### Step 2: Backend — SSH Client Utility

**New file:** `backend/src/eva_platform/ssh_client.py`

Async SSH client using `asyncssh` for connecting to Hetzner hosts.

```python
class InfraSSHClient:
    """Async SSH client for infrastructure operations on OpenClaw hosts."""

    async def _connect(self, host_ip: str) -> asyncssh.SSHClientConnection
        # Connect using EVA_SSH_PRIVATE_KEY_BASE64
        # known_hosts=None (hosts are ephemeral Hetzner servers)
        # username="root"

    async def run_command(self, host_ip: str, command: str, timeout: int = 30) -> str
        # Run remote command, return stdout

    async def docker_status(self, host_ip: str) -> list[dict]
        # Run: docker ps -a --format json
        # Parse NDJSON output into list of container dicts

    async def docker_logs(self, host_ip: str, container_name: str, tail: int = 100) -> str
        # Run: docker logs --tail {tail} {container_name} 2>&1
        # Return combined stdout+stderr

    async def list_directory(self, host_ip: str, path: str = "/root/.openclaw/") -> list[dict]
        # SFTP listdir with attrs (name, size, type, mtime)
        # Returns: [{name, size, is_dir, modified_at}, ...]

    async def read_file(self, host_ip: str, path: str, max_bytes: int = 1_048_576) -> str
        # SFTP read file content (cap at 1MB)
        # Returns file content as string
```

Key design:
- Uses `EVA_SSH_PRIVATE_KEY_BASE64` env var (decoded to temp file on first use)
- Connection per-request (no pooling needed — SSH multiplexing handles concurrent ops)
- All methods are async, timeout-protected
- Container name validation to prevent command injection

- [ ] Create `ssh_client.py`
- [ ] Add `asyncssh>=2.22.0` to `requirements.txt`

---

### Step 3: Backend — Pydantic Schemas

**File:** `backend/src/eva_platform/schemas.py`

Add infrastructure response schemas:

```python
# Host list response
class RuntimeHostResponse(BaseModel):
    id: UUID
    provider_host_id: str
    name: str
    region: str
    host_class: str
    state: str
    public_ip: str
    vcpu: int
    ram_mb: int
    disk_gb: int
    max_tenants: int
    tenant_count: int        # computed: count of active allocations
    saturation: float
    last_heartbeat_at: datetime | None

# Employee in host context
class RuntimeEmployeeResponse(BaseModel):
    id: UUID                 # openclaw_agent.id
    agent_id: UUID
    account_id: UUID
    label: str
    status: str
    phone_number: str | None
    allocation_state: str | None
    container_name: str | None
    gateway_port: int | None
    cpu_reservation_mcpu: int | None
    ram_reservation_mb: int | None
    reconnect_risk: str | None
    whatsapp_connected: bool
    telegram_connected: bool
    vps_ip: str | None

# Employee detail (full debug info)
class RuntimeEmployeeDetailResponse(BaseModel):
    # Agent info
    id: UUID
    agent_id: UUID
    account_id: UUID
    label: str
    status: str
    status_detail: str | None
    error: str | None
    phone_number: str | None
    connections_state: dict
    whatsapp_connected: bool
    telegram_connected: bool
    provisioning_started_at: datetime | None
    provisioning_completed_at: datetime | None
    # Allocation info
    allocation_state: str | None
    container_name: str | None
    gateway_port: int | None
    host_name: str | None
    host_ip: str | None
    cpu_reservation_mcpu: int | None
    ram_reservation_mb: int | None
    reconnect_risk: str | None
    queued_reason: str | None
    placed_at: datetime | None
    started_at: datetime | None
    # Recent events
    recent_events: list[RuntimeEventResponse]

class RuntimeEventResponse(BaseModel):
    id: UUID
    source: str
    event_type: str
    severity: str
    reason_code: str | None
    payload: dict
    created_at: datetime

# Docker container status
class DockerContainerResponse(BaseModel):
    name: str
    state: str               # running, exited, etc.
    status: str              # "Up 2 hours", "Exited 5 min ago"
    ports: str
    image: str
    created_at: str

# File system entry
class FileEntryResponse(BaseModel):
    name: str
    path: str                # full path
    is_dir: bool
    size: int | None         # bytes, None for dirs
    modified_at: datetime | None

# File content
class FileContentResponse(BaseModel):
    path: str
    content: str
    size: int
    truncated: bool          # True if file was capped at 1MB
```

- [ ] Add schemas to `schemas.py`

---

### Step 4: Backend — Infrastructure Router

**New file:** `backend/src/eva_platform/router/infrastructure.py`

Seven endpoints:

```
GET  /infrastructure/hosts
  → Query openclaw_runtime_hosts (state != released)
  → Join to count allocations per host
  → Return list of RuntimeHostResponse

GET  /infrastructure/hosts/{host_id}/employees
  → Query openclaw_agents + allocations for given host
  → Return list of RuntimeEmployeeResponse

GET  /infrastructure/employees/{openclaw_agent_id}
  → Full employee detail with allocation + recent events (last 20)
  → Return RuntimeEmployeeDetailResponse

GET  /infrastructure/hosts/{host_ip}/docker/status
  → SSH to host, run docker ps -a --format json
  → Return list of DockerContainerResponse

GET  /infrastructure/hosts/{host_ip}/docker/logs/{container_name}
  → SSH to host, docker logs --tail 100 {container}
  → Query param: tail (default 100, max 500)
  → Return plain text (or {lines: str})

GET  /infrastructure/hosts/{host_ip}/files
  → SSH/SFTP to host, list directory
  → Query param: path (default /root/.openclaw/)
  → Return list of FileEntryResponse

GET  /infrastructure/hosts/{host_ip}/files/content
  → SSH/SFTP to host, read file
  → Query param: path (required)
  → Return FileContentResponse
```

Security:
- All endpoints use `get_current_user` dependency (standard ERP auth)
- Host IP validated against DB (only IPs from `openclaw_runtime_hosts` accepted)
- Container name validated (alphanumeric + hyphens only, prevent injection)
- File path sanitized (no `..` traversal outside root, though full filesystem access allowed)

- [ ] Create `infrastructure.py` router
- [ ] Register in `router/__init__.py`

---

### Step 5: Backend — Config & Env

**File:** `backend/src/common/config.py`

Add settings:
```python
eva_ssh_private_key_base64: str | None = None   # Base64-encoded SSH private key
hetzner_api_token: str | None = None            # For future Hetzner API integration
```

**File:** `backend/.env.example`

Add:
```env
# OpenClaw Infrastructure (SSH access to runtime hosts)
EVA_SSH_PRIVATE_KEY_BASE64=base64-encoded-private-key
HETZNER_API_TOKEN=your-hetzner-api-token
```

**File:** `backend/.env` (local dev)

Add actual values.

- [ ] Update config.py
- [ ] Update .env.example
- [ ] Update .env with actual values

---

### Step 6: Frontend — TypeScript Types

**File:** `frontend/src/types/index.ts`

Add interfaces:
```typescript
// Infrastructure
interface RuntimeHost {
  id: string
  provider_host_id: string
  name: string
  region: string
  host_class: string
  state: string
  public_ip: string
  vcpu: number
  ram_mb: number
  disk_gb: number
  max_tenants: number
  tenant_count: number
  saturation: number
  last_heartbeat_at: string | null
}

interface RuntimeEmployee {
  id: string
  agent_id: string
  account_id: string
  label: string
  status: string
  phone_number: string | null
  allocation_state: string | null
  container_name: string | null
  gateway_port: number | null
  cpu_reservation_mcpu: number | null
  ram_reservation_mb: number | null
  reconnect_risk: string | null
  whatsapp_connected: boolean
  telegram_connected: boolean
  vps_ip: string | null
}

interface RuntimeEmployeeDetail extends RuntimeEmployee {
  status_detail: string | null
  error: string | null
  connections_state: Record<string, unknown>
  provisioning_started_at: string | null
  provisioning_completed_at: string | null
  allocation_state: string | null
  container_name: string | null
  gateway_port: number | null
  host_name: string | null
  host_ip: string | null
  queued_reason: string | null
  placed_at: string | null
  started_at: string | null
  recent_events: RuntimeEvent[]
}

interface RuntimeEvent {
  id: string
  source: string
  event_type: string
  severity: string
  reason_code: string | null
  payload: Record<string, unknown>
  created_at: string
}

interface DockerContainer {
  name: string
  state: string
  status: string
  ports: string
  image: string
  created_at: string
}

interface FileEntry {
  name: string
  path: string
  is_dir: boolean
  size: number | null
  modified_at: string | null
}

interface FileContent {
  path: string
  content: string
  size: number
  truncated: boolean
}
```

- [ ] Add types

---

### Step 7: Frontend — API Client

**File:** `frontend/src/lib/api/eva-platform.ts`

Add infrastructure methods:
```typescript
// Infrastructure
listHosts: () => api.get("/eva-platform/infrastructure/hosts").then(r => r.data),
listHostEmployees: (hostId: string) =>
  api.get(`/eva-platform/infrastructure/hosts/${hostId}/employees`).then(r => r.data),
getEmployeeDetail: (agentId: string) =>
  api.get(`/eva-platform/infrastructure/employees/${agentId}`).then(r => r.data),
getDockerStatus: (hostIp: string) =>
  api.get(`/eva-platform/infrastructure/hosts/${hostIp}/docker/status`).then(r => r.data),
getDockerLogs: (hostIp: string, containerName: string, tail?: number) =>
  api.get(`/eva-platform/infrastructure/hosts/${hostIp}/docker/logs/${containerName}`,
    { params: { tail } }).then(r => r.data),
listFiles: (hostIp: string, path?: string) =>
  api.get(`/eva-platform/infrastructure/hosts/${hostIp}/files`,
    { params: { path } }).then(r => r.data),
getFileContent: (hostIp: string, path: string) =>
  api.get(`/eva-platform/infrastructure/hosts/${hostIp}/files/content`,
    { params: { path } }).then(r => r.data),
```

- [ ] Add API methods

---

### Step 8: Frontend — Infrastructure Page

**New file:** `frontend/src/app/(app)/infrastructure/page.tsx`

Two-panel layout with detail sheet:

```
┌─────────────────────────────────────────────────────────────────┐
│  Infrastructure · OpenClaw runtime hosts and employees          │
├──────────────────────┬──────────────────────────────────────────┤
│  HOSTS               │  EMPLOYEES ON: openclaw-host-520b17a6    │
│                      │                                          │
│  ┌────────────────┐  │  ┌──────────────────────────────────────┐│
│  │ openclaw-host-… │  │  │ Eva (fmaccesorios)                  ││
│  │ 116.203.142.60  │  │  │ active · gateway-abc123 · port 18789││
│  │ ████████░░ 3/8  │  │  │ WhatsApp ● Telegram ○               ││
│  │ active · 2m ago │  │  └──────────────────────────────────────┘│
│  └────────────────┘  │  ┌──────────────────────────────────────┐│
│                      │  │ Eva (EvaAI)                           ││
│  (more hosts...)     │  │ active · gateway-def456 · port 18791 ││
│                      │  │ WhatsApp ● Telegram ●                 ││
│                      │  └──────────────────────────────────────┘│
│                      │  ┌──────────────────────────────────────┐│
│                      │  │ Eva 2 (EvaAI)                         ││
│                      │  │ active · gateway-ghi789 · port 18793 ││
│                      │  │ WhatsApp ○ Telegram ○                 ││
│                      │  └──────────────────────────────────────┘│
│                      │                                          │
│                      │  5 slots available                       │
└──────────────────────┴──────────────────────────────────────────┘
```

**State management:**
```typescript
const [hosts, setHosts] = useState<RuntimeHost[]>([])
const [selectedHost, setSelectedHost] = useState<RuntimeHost | null>(null)
const [employees, setEmployees] = useState<RuntimeEmployee[]>([])
const [selectedEmployee, setSelectedEmployee] = useState<RuntimeEmployee | null>(null)
const [sheetOpen, setSheetOpen] = useState(false)
const [loading, setLoading] = useState(true)
```

**Auto-refresh:** Every 30 seconds (matches monitoring page pattern).

**Interactions:**
1. Click host card → load employees for that host (right panel)
2. Click employee row → open detail sheet (slide-over)
3. Detail sheet has 4 tabs: Info, Docker, Logs, Files

- [ ] Create infrastructure page

---

### Step 9: Frontend — Employee Detail Sheet

Slide-over sheet (right side, ~600px wide) with 4 tabs:

**Tab 1: Info**
- Employee label, status badge, account ID
- Phone number, channel states (WhatsApp/Telegram with connected indicators)
- Allocation state, container name, gateway port
- Host name, host IP
- Provisioning timestamps
- Recent events table (last 20, severity-colored)

**Tab 2: Docker**
- Fetched on-demand via SSH (loading state while fetching)
- Container cards showing: name, state, status, ports, image
- Gateway container highlighted (primary)
- Browser sidecar shown if exists

**Tab 3: Logs**
- Terminal-style panel (dark background, monospace font)
- Last 100 lines of gateway container logs
- Fetched on-demand via SSH
- Scrollable, auto-scroll to bottom
- Refresh button to reload

**Tab 4: Files**
- Split view: file tree (left ~40%) + file viewer (right ~60%)
- Default path: `/root/.openclaw/`
- Breadcrumb navigation at top
- Click directory → expand/navigate
- Click file → show content in viewer
- Syntax highlighting for `.json`, `.yaml`, `.md`, `.js`, `.mjs` files
- File size and modification time shown

- [ ] Create detail sheet component (or inline in page)

---

### Step 10: Frontend — Sidebar Update

**File:** `frontend/src/components/layout/sidebar.tsx`

Add "Infrastructure" item to the "Eva Platform" group:

```typescript
{
  name: "Infrastructure",
  href: "/infrastructure",
  icon: Server,  // from lucide-react
  phase: 8,
}
```

Position: After "Monitoring" in the Eva Platform group.

- [ ] Add sidebar item

---

### Step 11: Frontend — Layout Title

**File:** `frontend/src/app/(app)/layout.tsx`

Add to `PAGE_TITLES`:
```typescript
"/infrastructure": {
  title: "Infrastructure",
  subtitle: "OpenClaw runtime hosts and employees",
},
```

- [ ] Add page title mapping

---

### Step 12: Environment Setup

**Local dev `.env`:**
```env
EVA_SSH_PRIVATE_KEY_BASE64=<base64 of ~/.ssh/id_ed25519_eva>
HETZNER_API_TOKEN=<dev project token>
```

**Production (Koyeb):**
```env
EVA_SSH_PRIVATE_KEY_BASE64=<base64 of eva-deploy private key>
HETZNER_API_TOKEN=<production project token>
```

- [ ] Set up local env vars
- [ ] Document production env vars needed

---

## File Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/src/eva_platform/models.py` | Edit | Add 4 OpenClaw mirror models |
| `backend/src/eva_platform/schemas.py` | Edit | Add infrastructure response schemas |
| `backend/src/eva_platform/ssh_client.py` | **New** | Async SSH client (asyncssh) |
| `backend/src/eva_platform/router/infrastructure.py` | **New** | 7 infrastructure endpoints |
| `backend/src/eva_platform/router/__init__.py` | Edit | Register infrastructure router |
| `backend/src/common/config.py` | Edit | Add SSH + Hetzner settings |
| `backend/requirements.txt` | Edit | Add `asyncssh>=2.22.0` |
| `backend/.env.example` | Edit | Add SSH + Hetzner vars |
| `frontend/src/types/index.ts` | Edit | Add infrastructure types |
| `frontend/src/lib/api/eva-platform.ts` | Edit | Add infrastructure API methods |
| `frontend/src/app/(app)/infrastructure/page.tsx` | **New** | Infrastructure page |
| `frontend/src/components/layout/sidebar.tsx` | Edit | Add Infrastructure nav item |
| `frontend/src/app/(app)/layout.tsx` | Edit | Add page title |

---

## Security Considerations

1. **Host IP validation** — Only accept IPs that exist in `openclaw_runtime_hosts` table
2. **Container name validation** — Alphanumeric + hyphens only (prevent shell injection)
3. **File path sanitization** — Reject `..` in path components (prevent traversal attacks)
4. **Read-only** — No write operations on hosts (Phase 1)
5. **File size cap** — 1MB max for file content reads
6. **SSH timeout** — 30s default, prevent hanging connections
7. **No secrets exposure** — SSH key stays server-side, never sent to frontend

---

## Phase 2 (Future)

- Host actions: drain, restart container, redeploy employee
- Hetzner API metrics: real CPU/RAM/bandwidth charts
- Log streaming (WebSocket for live logs)
- Config editing (write openclaw.json changes)
- Alert integration (Slack notifications for host issues)
