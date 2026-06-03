"""Skill zip 上传接口实机测试（api_tester 不支持 multipart）。"""
from __future__ import annotations

import io
import json
import sys
import uuid
import zipfile

import requests

BASE = "http://127.0.0.1:8000/api/v1/agent"
UPLOAD_URL = f"{BASE}/skills/upload"


def _skill_md(name: str) -> str:
    return f"""---
name: {name}
description: zip 上传测试
always: false
---
# {name}
"""


def main() -> int:
    uid = uuid.uuid4().hex[:8]
    skill_name = f"zip-api-{uid}"
    files = {
        "SKILL.md": _skill_md(skill_name),
        "references/note.md": "# note",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content.encode("utf-8"))
    buf.seek(0)

    print(f"\n【Zip 上传】POST {UPLOAD_URL}")
    resp = requests.post(
        UPLOAD_URL,
        files={"file": (f"{skill_name}.zip", buf, "application/zip")},
        timeout=30,
    )
    print(f"HTTP {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))

    failed = 0
    if data.get("code") != 0:
        print("[FAIL] 业务码非 0")
        failed += 1
    else:
        skills = (data.get("data") or {}).get("skills") or []
        if not skills or skills[0].get("name") != skill_name:
            print(f"[FAIL] 返回 skill 名称不符，期望 {skill_name}")
            failed += 1
        else:
            skill_id = skills[0]["skill_id"]
            print(f"[PASS] 上传成功 skill_id={skill_id}")

            detail_url = f"{BASE}/skills/{skill_id}"
            d = requests.get(detail_url, timeout=30).json()
            if d.get("code") != 0:
                print("[FAIL] 上传后查询详情失败")
                failed += 1
            else:
                print(f"[PASS] 详情查询 name={d['data']['name']} file_count={len(d['data']['files'])}")

            del_resp = requests.delete(detail_url, timeout=30).json()
            if del_resp.get("code") != 0:
                print(f"[WARN] 清理删除失败: {del_resp.get('message')}")
            else:
                print("[PASS] 已清理上传的测试 Skill")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
