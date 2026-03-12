import asyncio
import logging
from datetime import datetime

import docker
from docker.errors import DockerException, NotFound

from beanie.operators import Set

from app.core.config import settings
from app.models.action.sandbox import SandboxModel
from app.schemas.constants import SandboxStatusEnum, SandboxTypeEnum
from app.utils.id_lib import generate_id

logger = logging.getLogger(__name__)

SANDBOX_LABEL = {"csi.sandbox": "true"}


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


def create_sandbox(display_name: str | None = None, type: SandboxTypeEnum = SandboxTypeEnum.ALL_IN_ONE) -> tuple[bool, str, dict | None]:
    if type == SandboxTypeEnum.ALL_IN_ONE:
        if not settings.AIO_SANDBOX_IMAGE or not settings.AIO_SANDBOX_IMAGE.strip():
            return False, "未配置 AIO_SANDBOX_IMAGE", None
        try:
            client = get_docker_client()
            host_port = _pick_host_port(client)
            if host_port is None:
                return False, "端口池耗尽，无可用端口", None
            container_name = f"csi-sandbox-{host_port}"
            container = client.containers.create(
                settings.AIO_SANDBOX_IMAGE.strip(),
                labels=SANDBOX_LABEL,
                ports={"8080/tcp": host_port},
                name=container_name,
                security_opt=["seccomp=unconfined"],
                shm_size="2g",
                environment={
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
                "display_name": display_name.strip() if display_name and display_name.strip() else None,
                "host_port": host_port,
                "status": container.status,
                "sandbox_status": SandboxStatusEnum.CREATED,
                "created_at": created_at,
                "image": settings.AIO_SANDBOX_IMAGE.strip(),
            }
        except DockerException as e:
            logger.exception("创建沙盒失败")
            return False, str(e) or "创建沙盒失败", None
    elif type == SandboxTypeEnum.WINDOWS:
        if not settings.WINDOWS_SANDBOX_IMAGE or not settings.WINDOWS_SANDBOX_IMAGE.strip():
            return False, "未配置 WINDOWS_SANDBOX_IMAGE", None
        template_vol = (settings.WINDOWS_TEMPLATE_VOLUME or "").strip() or "win_template_vol"
        try:
            client = get_docker_client()
            host_port = _pick_host_port(client)
            if host_port is None:
                return False, "端口池耗尽，无可用端口", None
            container_name = f"csi-win-sandbox-{host_port}"
            data_volume_name = f"win_vol_{host_port}"
            client.volumes.create(name=data_volume_name, labels=SANDBOX_LABEL)
            create_kw = {
                "image": settings.WINDOWS_SANDBOX_IMAGE.strip(),
                "name": container_name,
                "labels": {**SANDBOX_LABEL, "csi.win.volume": data_volume_name},
                "ports": {"8006/tcp": host_port},
                "volumes": {data_volume_name: {"bind": "/storage", "mode": "rw"}},
                "cap_add": ["NET_ADMIN"],
            }
            try:
                container = client.containers.create(**create_kw, devices=["/dev/kvm"])
            except DockerException:
                container = client.containers.create(**create_kw)
            created = container.attrs.get("Created") or ""
            try:
                created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                created_at = None
            return True, container.short_id, {
                "sandbox_id": container.short_id,
                "name": container.name,
                "display_name": display_name.strip() if display_name and display_name.strip() else None,
                "host_port": host_port,
                "status": container.status,
                "sandbox_status": SandboxStatusEnum.CREATED,
                "created_at": created_at,
                "image": settings.WINDOWS_SANDBOX_IMAGE.strip(),
            }
        except DockerException as e:
            logger.exception("创建 Windows 沙盒失败")
            return False, str(e) or "创建 Windows 沙盒失败", None
    else:
        return False, "不支持的沙盒类型", None


def _start_sandbox(container_id: str, image_type: SandboxTypeEnum) -> None:
    client = get_docker_client()
    if image_type == SandboxTypeEnum.WINDOWS:
        container = client.containers.get(container_id)
        labels = (container.attrs.get("Config") or {}).get("Labels") or {}
        data_volume_name = (labels.get("csi.win.volume") or "").strip()
        template_vol = (settings.WINDOWS_TEMPLATE_VOLUME or "").strip() or "win_template_vol"
        client.containers.run(
            "alpine",
            command=["sh", "-c", "apk add --no-cache coreutils && cp -a --sparse=always /src/. /dest/ && rm -f /dest/windows.mac"],
            remove=True,
            volumes={
                template_vol: {"bind": "/src", "mode": "ro"},
                data_volume_name: {"bind": "/dest", "mode": "rw"},
            },
        )
        container.start()
    else:
        client.containers.get(container_id).start()


async def start_sandbox_and_update_status(container_id: str, image_type: SandboxTypeEnum) -> None:
    try:
        await asyncio.to_thread(_start_sandbox, container_id, image_type)
        await update_sandbox_doc_status(container_id, SandboxStatusEnum.DEPLOYED)
    except Exception:
        logger.exception("后台启动沙盒失败，容器ID: %s", container_id)


async def update_sandbox_doc_status(container_id: str, status: SandboxStatusEnum) -> None:
    doc = await SandboxModel.find_one(SandboxModel.container_id == container_id)
    if doc:
        await doc.update(Set({
            SandboxModel.sandbox_status: status,
            SandboxModel.updated_at: datetime.now(),
        }))


def delete_sandbox(sandbox_id: str, image_type: SandboxTypeEnum) -> tuple[bool, str]:
    if not sandbox_id or not sandbox_id.strip():
        return False, "沙盒ID不能为空"
    try:
        client = get_docker_client()
        container = client.containers.get(sandbox_id.strip())
        labels = (container.attrs.get("Config") or {}).get("Labels") or {}
        if labels.get("csi.sandbox") != "true":
            return False, "仅允许删除本系统创建的沙盒容器"
        volume_name = (labels.get("csi.win.volume") or "").strip() or None
        try:
            container.kill(signal="SIGKILL")
        except DockerException:
            pass
        container.remove()
        if volume_name:
            try:
                client.volumes.get(volume_name).remove()
            except (NotFound, DockerException):
                pass
        return True, "success"
    except NotFound:
        return False, "沙盒不存在"
    except DockerException as e:
        logger.exception("销毁沙盒失败")
        return False, str(e) or "销毁沙盒失败"


def _get_container_info(container_id: str, detail: bool = False) -> dict | None:
    try:
        client = get_docker_client()
        container = client.containers.get(container_id.strip())
        labels = (container.attrs.get("Config") or {}).get("Labels") or {}
        if labels.get("csi.sandbox") != "true":
            return None
        host_port = None
        ports = {}
        bindings = (container.attrs.get("HostConfig") or {}).get("PortBindings") or {}
        for container_port, port_list in bindings.items():
            for b in port_list:
                hp = b.get("HostPort")
                if hp:
                    try:
                        if detail:
                            ports[container_port] = int(hp)
                        if host_port is None and ("8080" in container_port or "8006" in container_port):
                            host_port = int(hp)
                    except ValueError:
                        if detail:
                            ports[container_port] = hp
                        if host_port is None and ("8080" in container_port or "8006" in container_port):
                            host_port = hp
        created = (container.attrs.get("Created") or "").replace("Z", "+00:00")
        try:
            created_at = datetime.fromisoformat(created)
        except Exception:
            created_at = None
        image = (container.attrs.get("Config") or {}).get("Image") or ""
        out = {
            "status": container.status,
            "name": container.name,
            "image": image,
            "host_port": host_port,
            "created_at": created_at,
        }
        if detail:
            out["ports"] = ports
            out["labels"] = dict(labels)
        return out
    except (NotFound, DockerException):
        return None


def _get_container_infos_batch(container_ids: list[str], detail: bool = False) -> dict[str, dict | None]:
    return {cid: _get_container_info(cid, detail) for cid in container_ids}


async def insert_sandbox_doc(
    container_id: str,
    container_name: str,
    image_type: SandboxTypeEnum,
    display_name: str | None,
    host_port: int,
    image: str,
    created_at: datetime | None,
    sandbox_status: SandboxStatusEnum = SandboxStatusEnum.CREATED,
) -> None:
    now = datetime.now()
    doc = SandboxModel(
        id=generate_id(container_id + container_name + str(now.timestamp())),
        container_id=container_id,
        container_name=container_name,
        image_type=image_type,
        display_name=display_name,
        host_port=host_port,
        image=image,
        sandbox_status=sandbox_status,
        created_at=created_at or now,
        updated_at=now,
    )
    await doc.insert()


async def delete_sandbox_doc_by_container_id(container_id: str) -> None:
    doc = await SandboxModel.find_one(SandboxModel.container_id == container_id)
    if doc:
        await doc.delete()


async def get_sandbox_doc_by_container_id(container_id: str) -> SandboxModel | None:
    return await SandboxModel.find_one(SandboxModel.container_id == container_id)


async def list_sandboxes_from_db(skip: int, limit: int) -> tuple[list[dict], int]:
    query = SandboxModel.find().sort([("created_at", -1)])
    total = await query.count()
    docs = await query.skip(skip).limit(limit).to_list()
    if not docs:
        return [], total
    container_ids = [d.container_id for d in docs]
    infos = await asyncio.to_thread(_get_container_infos_batch, container_ids, False)
    result = []
    for d in docs:
        info = infos.get(d.container_id)
        if info:
            result.append({
                "sandbox_id": d.container_id,
                "name": info["name"],
                "display_name": d.display_name,
                "image_type": d.image_type,
                "status": info["status"],
                "sandbox_status": d.sandbox_status,
                "image": info["image"],
                "host_port": info["host_port"],
                "created_at": d.created_at,
            })
        else:
            result.append({
                "sandbox_id": d.container_id,
                "name": d.container_name,
                "display_name": d.display_name,
                "image_type": d.image_type,
                "status": "removed",
                "sandbox_status": d.sandbox_status,
                "image": d.image,
                "host_port": d.host_port,
                "created_at": d.created_at,
            })
    return result, total


async def get_sandbox_detail_from_db(sandbox_id: str) -> tuple[bool, str, dict | None]:
    if not sandbox_id or not sandbox_id.strip():
        return False, "沙盒ID不能为空", None
    doc = await SandboxModel.find_one(SandboxModel.container_id == sandbox_id.strip())
    if not doc:
        return False, "沙盒不存在", None
    info = await asyncio.to_thread(_get_container_info, sandbox_id.strip(), True)
    if info:
        data = {
            "sandbox_id": doc.container_id,
            "name": info["name"],
            "display_name": doc.display_name,
            "image_type": doc.image_type,
            "status": info["status"],
            "sandbox_status": doc.sandbox_status,
            "image": info["image"],
            "host_port": info["host_port"],
            "created_at": doc.created_at,
            "ports": info.get("ports", {}),
            "labels": info.get("labels", {}),
        }
    else:
        data = {
            "sandbox_id": doc.container_id,
            "name": doc.container_name,
            "display_name": doc.display_name,
            "image_type": doc.image_type,
            "status": "removed",
            "sandbox_status": doc.sandbox_status,
            "image": doc.image,
            "host_port": doc.host_port,
            "created_at": doc.created_at,
            "ports": {},
            "labels": {},
        }
    return True, "success", data
