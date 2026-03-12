import logging
from datetime import datetime

import docker
from docker.errors import DockerException, NotFound

from app.core.config import settings

logger = logging.getLogger(__name__)

SANDBOX_LABEL = {"csi.sandbox": "true"}
CONTAINER_PORT = 8080


def _parse_port_range(port_range: str) -> list[int]:
    if not port_range or not port_range.strip():
        return []
    result = []
    for part in port_range.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                low, high = int(a.strip()), int(b.strip())
                if 1 <= low <= 65535 and 1 <= high <= 65535 and low <= high:
                    result.extend(range(low, high + 1))
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= 65535:
                    result.append(p)
            except ValueError:
                continue
    seen = set()
    out = []
    for p in sorted(result):
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def get_docker_client() -> docker.DockerClient:
    if settings.DOCKER_HOST and settings.DOCKER_HOST.strip():
        return docker.DockerClient(base_url=settings.DOCKER_HOST.strip())
    return docker.from_env()


def _get_used_host_ports(client: docker.DockerClient) -> set[int]:
    used = set()
    try:
        containers = client.containers.list(all=True)
        for c in containers:
            bindings = (c.attrs.get("HostConfig") or {}).get("PortBindings") or {}
            for port_list in bindings.values():
                for b in port_list:
                    hp = b.get("HostPort")
                    if hp:
                        try:
                            used.add(int(hp))
                        except ValueError:
                            pass
    except DockerException:
        pass
    return used


def _pick_host_port(client: docker.DockerClient) -> int | None:
    candidates = _parse_port_range(settings.SANDBOX_PORT_RANGE)
    if not candidates:
        return None
    used = _get_used_host_ports(client)
    for p in candidates:
        if p not in used:
            return p
    return None


def create_sandbox() -> tuple[bool, str, dict | None]:
    if not settings.SANDBOX_IMAGE or not settings.SANDBOX_IMAGE.strip():
        return False, "未配置 SANDBOX_IMAGE", None
    try:
        client = get_docker_client()
        host_port = _pick_host_port(client)
        if host_port is None:
            return False, "端口池耗尽，无可用端口", None
        name = f"csi-sandbox-{host_port}"
        container = client.containers.run(
            settings.SANDBOX_IMAGE.strip(),
            detach=True,
            labels=SANDBOX_LABEL,
            ports={"8080/tcp": host_port},
            name=name,
            security_opt=["seccomp=unconfined"],
            shm_size="2g",
            environment={
                # 代理暂时写死，后续代理功能完善后补充
                "PROXY_SERVER": "http://192.168.31.200:7890",
            },
        )
        created = container.attrs.get("Created") or ""
        try:
            created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            created_at = None
        return True, container.short_id, {
            "sandbox_id": container.short_id,
            "name": container.name,
            "host_port": host_port,
            "status": container.status,
            "created_at": created_at,
            "image": settings.SANDBOX_IMAGE.strip(),
        }
    except DockerException as e:
        logger.exception("创建沙盒失败")
        return False, str(e) or "创建沙盒失败", None


def delete_sandbox(sandbox_id: str) -> tuple[bool, str]:
    if not sandbox_id or not sandbox_id.strip():
        return False, "沙盒ID不能为空"
    try:
        client = get_docker_client()
        container = client.containers.get(sandbox_id.strip())
        labels = (container.attrs.get("Config") or {}).get("Labels") or {}
        if labels.get("csi.sandbox") != "true":
            return False, "仅允许删除本系统创建的沙盒容器"
        container.stop()
        container.remove()
        return True, "success"
    except NotFound:
        return False, "沙盒不存在"
    except DockerException as e:
        logger.exception("销毁沙盒失败")
        return False, str(e) or "销毁沙盒失败"


def list_sandboxes(skip: int, limit: int) -> tuple[list[dict], int]:
    try:
        client = get_docker_client()
        containers = client.containers.list(all=True, filters={"label": "csi.sandbox=true"})
        total = len(containers)
        result = []
        for c in containers[skip : skip + limit]:
            host_port = None
            bindings = (c.attrs.get("HostConfig") or {}).get("PortBindings") or {}
            for port_list in bindings.values():
                for b in port_list:
                    hp = b.get("HostPort")
                    if hp:
                        try:
                            host_port = int(hp)
                            break
                        except ValueError:
                            pass
                if host_port is not None:
                    break
            created = (c.attrs.get("Created") or "").replace("Z", "+00:00")
            try:
                created_at = datetime.fromisoformat(created)
            except Exception:
                created_at = None
            image = (c.attrs.get("Config") or {}).get("Image") or ""
            result.append({
                "sandbox_id": c.short_id,
                "name": c.name,
                "status": c.status,
                "image": image,
                "host_port": host_port,
                "created_at": created_at,
            })
        return result, total
    except DockerException as e:
        logger.exception("列出沙盒失败")
        return [], 0


def get_sandbox_detail(sandbox_id: str) -> tuple[bool, str, dict | None]:
    if not sandbox_id or not sandbox_id.strip():
        return False, "沙盒ID不能为空", None
    try:
        client = get_docker_client()
        container = client.containers.get(sandbox_id.strip())
        labels = (container.attrs.get("Config") or {}).get("Labels") or {}
        if labels.get("csi.sandbox") != "true":
            return False, "仅允许查询本系统创建的沙盒容器", None
        host_port = None
        ports = {}
        bindings = (container.attrs.get("HostConfig") or {}).get("PortBindings") or {}
        for container_port, port_list in bindings.items():
            for b in port_list:
                hp = b.get("HostPort")
                if hp:
                    try:
                        ports[container_port] = int(hp)
                        if host_port is None and "8080" in container_port:
                            host_port = int(hp)
                    except ValueError:
                        ports[container_port] = hp
                        if host_port is None and "8080" in container_port:
                            host_port = hp
        created = (container.attrs.get("Created") or "").replace("Z", "+00:00")
        try:
            created_at = datetime.fromisoformat(created)
        except Exception:
            created_at = None
        image = (container.attrs.get("Config") or {}).get("Image") or ""
        return True, "success", {
            "sandbox_id": container.short_id,
            "name": container.name,
            "status": container.status,
            "image": image,
            "host_port": host_port,
            "created_at": created_at,
            "ports": ports,
            "labels": dict(labels),
        }
    except NotFound:
        return False, "沙盒不存在", None
    except DockerException as e:
        logger.exception("查询沙盒详情失败")
        return False, str(e) or "查询沙盒详情失败", None
