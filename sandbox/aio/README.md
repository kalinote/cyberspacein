# CSI Sandbox AIO

All-in-One Agent 沙箱环境——在单个 Docker 容器内集成浏览器、终端、文件操作、VSCode Server、Jupyter 与 MCP 服务。

本仓库基于 [agent-infra/sandbox](https://github.com/agent-infra/sandbox) 逆向还原的镜像方案进行二次开发，**不再依赖**官方预构建镜像 `ghcr.io/agent-infra/sandbox`，改为从 `docker/` 目录自建镜像 **`csi-sandbox-aio`**。

## 功能概览

| 能力 | 说明 |
|------|------|
| 浏览器 + VNC | Chrome CDP 自动化、远程桌面 |
| Shell / 文件 | HTTP API + WebSocket 终端 |
| VSCode Server | 浏览器内完整 IDE |
| JupyterLab | 交互式 Python 执行 |
| MCP Hub | 预置 browser / file / shell / markitdown 等 MCP 服务 |
| 统一文件系统 | 浏览器下载的文件可直接在 Shell / 文件中访问 |

容器内由 **supervisord** 编排各服务，nginx 在 `:8080` 统一对外暴露网关。

## 仓库结构

```
aio/
├── docker/                 # 镜像构建（Dockerfile + 逆向还原的 context）
│   ├── Dockerfile
│   ├── context/
│   │   ├── python-server/  # 沙箱 HTTP/MCP 后端
│   │   ├── browser-sdk/
│   │   ├── repl-servers/
│   │   ├── aio/              # aio CLI 源码
│   │   └── rootfs/           # 编排脚本、nginx/supervisord 配置
│   └── requirements/         # 各 Python 环境的 pip 锁定列表
├── sdk/python/             # Python SDK（本仓库唯一保留的 SDK）
├── examples/               # Python 集成示例
└── evaluation/             # MCP / Agent 评测数据集
```

已移除、不在本仓库维护的内容：官方 `website/` 文档站、JS/Go SDK、`docker-compose.yaml`、Volcengine Provider 示例、根目录 Monorepo 工具链配置。

## 快速开始

### 1. 构建镜像

构建上下文为 `docker/` 目录：

```bash
docker build -t csi-sandbox-aio -f docker/Dockerfile docker/
```

首次构建耗时较长（下载 Python/Node/Chrome 等依赖）。建议开启 BuildKit：

```bash
export DOCKER_BUILDKIT=1
docker build -t csi-sandbox-aio -f docker/Dockerfile docker/
```

多架构构建可显式指定平台：

```bash
docker build --platform linux/amd64 -t csi-sandbox-aio -f docker/Dockerfile docker/
```

若从 GitHub 下载资源时出现 `curl (56) SSL` 错误，属于网络抖动，重试构建即可；也可在 Dockerfile 的 `curl` 命令上增加 `--retry` 参数。

### 2. 运行容器

```bash
docker run --rm -d --name csi-sandbox-aio \
  -p 8080:8080 \
  --shm-size=2g \
  --security-opt seccomp=unconfined \
  csi-sandbox-aio
```

查看启动日志：

```bash
docker logs -f csi-sandbox-aio
```

### 3. 访问服务

| 入口 | URL |
|------|-----|
| 控制台 / 网关 | http://localhost:8080/ |
| API 文档 (Swagger) | http://localhost:8080/v1/docs |
| VNC 浏览器 | http://localhost:8080/vnc/index.html?autoconnect=true |
| VSCode Server | http://localhost:8080/code-server/ |
| MCP Hub | http://localhost:8080/mcp |

### 4. 冒烟测试

```bash
curl -s http://localhost:8080/v1/sandbox

curl -s -X POST http://localhost:8080/v1/shell/exec \
  -H "Content-Type: application/json" \
  -d '{"command":"echo hello"}'
```

## Python SDK

本仓库仅保留 Python SDK，位于 `sdk/python/`。

### 安装

从源码安装（推荐开发时使用）：

```bash
cd sdk/python
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -e .
```

或从 PyPI 安装上游包（包名仍为 `agent-sandbox`，API 兼容）：

```bash
pip install agent-sandbox
```

### 基本用法

```python
from agent_sandbox import Sandbox

client = Sandbox(base_url="http://localhost:8080")
home_dir = client.sandbox.get_context().home_dir

result = client.shell.exec_command(command="ls -la")
print(result.data.output)

content = client.file.read_file(file=f"{home_dir}/.bashrc")
print(content.data.content)

screenshot = client.browser.screenshot()
```

更多示例见 [`examples/`](examples/) 目录。

## 本地开发（无 Docker 环境）

若开发机为 Windows + VSCode 且本地无 Docker，可将代码同步到有 Docker 的远程 Linux 机器构建测试。

**推荐：VS Code Remote-SSH**

1. 安装 Remote - SSH 扩展，连接远程开发机
2. 在远端打开本仓库，于集成终端执行 `docker build` / `docker run`
3. 通过 SSH 端口转发访问 `localhost:8080`

**备选：Git 推送 + 远端构建**

```powershell
git push origin <branch>
ssh user@remote-host "cd ~/workspace/sandbox/aio && git pull && docker build -t csi-sandbox-aio -f docker/Dockerfile docker/"
```

本地 Windows 可用 `sdk/python/.venv` 中的 SDK 连接远端沙箱：

```python
from agent_sandbox import Sandbox
client = Sandbox(base_url="http://<远端IP>:8080")
```

修改 `docker/context/python-server/` 后需重新 `docker build` 才能生效。

## 部署

### Docker Run（常用环境变量）

```bash
docker run -d --name csi-sandbox-aio \
  -p 8080:8080 \
  --shm-size=2g \
  --security-opt seccomp=unconfined \
  -e WORKSPACE=/home/gem \
  -e TZ=Asia/Singapore \
  -e PROXY_SERVER=host.docker.internal:7890 \
  csi-sandbox-aio
```

### Docker Compose 示例

```yaml
services:
  sandbox:
    container_name: csi-sandbox-aio
    image: csi-sandbox-aio
    security_opt:
      - seccomp:unconfined
    shm_size: "2gb"
    ports:
      - "8080:8080"
    environment:
      WORKSPACE: /home/gem
      TZ: Asia/Singapore
    restart: unless-stopped
```

### Kubernetes 示例

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: csi-sandbox-aio
spec:
  replicas: 1
  selector:
    matchLabels:
      app: csi-sandbox-aio
  template:
    metadata:
      labels:
        app: csi-sandbox-aio
    spec:
      containers:
        - name: csi-sandbox-aio
          image: csi-sandbox-aio:latest
          ports:
            - containerPort: 8080
          resources:
            limits:
              memory: "2Gi"
              cpu: "1000m"
```

## API 参考

### 核心 HTTP API

| 端点 | 说明 |
|------|------|
| `GET /v1/sandbox` | 沙箱环境信息 |
| `POST /v1/shell/exec` | 执行 Shell 命令 |
| `GET/POST /v1/file/*` | 文件读写与操作 |
| `POST /v1/jupyter/execute` | 执行 Jupyter 代码 |
| `POST /v1/nodejs/execute` | 执行 Node.js 代码 |
| `POST /v1/browser/*` | 浏览器自动化 |

### MCP 服务

| 服务 | 工具示例 |
|------|----------|
| `browser` | navigate, screenshot, click, type |
| `file` | read, write, list, search |
| `shell` | exec, create_session |
| `markitdown` | convert, extract_text |

完整 API 文档在容器启动后访问 http://localhost:8080/v1/docs 。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    浏览器 + VNC (:6080)                      │
├─────────────────────────────────────────────────────────────┤
│  VSCode Server  │  Shell 终端  │  文件操作  │  Jupyter     │
├─────────────────────────────────────────────────────────────┤
│         python-server (:8091) + MCP Hub (/mcp)              │
├─────────────────────────────────────────────────────────────┤
│              nginx 网关 (:8080) + supervisord               │
└─────────────────────────────────────────────────────────────┘
```

容器入口为 `/opt/application/run.sh`（符号链接至 `/opt/gem/run.sh`），由 `run.sh` 初始化环境后启动 supervisord。

更详细的镜像重建说明、版本钉扎与服务端口表见 [`docker/README.md`](docker/README.md)。

## 本仓库定制说明

相对上游官方镜像，本仓库已做如下裁剪与改造：

- **自建镜像**：从 `docker/Dockerfile` 构建 `csi-sandbox-aio`，脱离 `ghcr.io/agent-infra/sandbox`
- **日志去字节化**：`python-server` 移除内网 `bytedlogger` / logid 链路，改用标准库 `logging` 输出到 stdout
- **裁剪 SDK**：仅保留 `sdk/python/`，移除 JS / Go SDK 及 Volcengine Provider
- **裁剪示例与工具**：移除 `website/`、`docker-compose.yaml`、根 Monorepo 配置等

## 集成示例

`examples/` 目录包含与 LangChain、OpenAI、Browser Use、Playwright、MiniMax 等框架的集成示例。运行前请先启动 `csi-sandbox-aio` 容器，并将示例中的 `base_url` 指向沙箱地址。

评测数据集与说明见 [`evaluation/`](evaluation/)。

## 致谢

本项目基于 [Agent Infra AIO Sandbox](https://github.com/agent-infra/sandbox) 逆向还原与二次开发，遵循 Apache License 2.0。
