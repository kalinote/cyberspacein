"""丰富 wiki-front-dev-seed 联调数据。用法: .venv\\Scripts\\python.exe scripts/enrich_wiki_seed.py"""
from __future__ import annotations

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000/api/v1"
SLUG = "wiki-front-dev-seed"
PAGE_ID = "15d75ca8-d8ec-40de-9006-0a79efef70b4"

S = {
    "creation": "42cb806ffe93c09179747b2e2b30a4c4",
    "voice": "6bc4daa66cc55f0bf5a0bec2af7abe3c",
    "anime": "80f2f926fbc7128d40cd6eb458615afd",
    "performance": "4169c8860230abd516f049a00741e623",
    "story": "05ffa502b3561e901d636624c6cb0218",
    "gameplay": "18d31789ceefd9ab1da37dde82285472",
    "reception": "a8a5d404176c79825998e4923f31afe7",
    "design": "37820a37a07e577a66fcad305cc21766",
}


def api(method: str, path: str, body: dict | None = None, query: str = "") -> dict:
    url = f"{BASE}{path}"
    if query:
        url += f"?{query}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"{method} {path}: {e.read().decode()}") from e


def rev() -> int:
    r = api("GET", f"/wiki/pages/by-slug/{SLUG}")
    if r.get("code") != 0:
        raise RuntimeError(r)
    return int(r["data"]["revision"])


def patch(path: str, body: dict, label: str) -> str | None:
    body["expectedRevision"] = rev()
    r = api("PATCH", path, body)
    if r.get("code") != 0:
        raise RuntimeError(f"{label}: {r}")
    print(f"OK {label}")
    return r.get("data", {}).get("section")


def post(path: str, body: dict, label: str) -> str | None:
    body["expectedRevision"] = rev()
    r = api("POST", path, body)
    if r.get("code") != 0:
        raise RuntimeError(f"{label}: {r}")
    sec = r.get("data", {}).get("section")
    print(f"OK {label} section={sec}")
    return sec


def put(path: str, body: dict, label: str) -> None:
    body["expectedRevision"] = rev()
    r = api("PUT", path, body)
    if r.get("code") != 0:
        raise RuntimeError(f"{label}: {r}")
    print(f"OK {label}")


def main() -> None:
    pid = PAGE_ID
    print(f"start revision={rev()}")

    patch(
        f"/wiki/pages/{pid}/main",
        {
            "content": (
                "**旅行者**（Traveler）是米哈游《原神》中由玩家操控的主角代称，"
                "通常指男性「空」或女性「荧」。作为跨越诸多世界的访客，"
                "旅行者在提瓦特追寻失散血亲，并卷入七国与天空岛相关的叙事。[^1][^2][^a][^b]\n\n"
                "玩法上，旅行者可通过七天神像掌握多种元素力，参与探索、解谜与战斗。[^3]"
            ),
            "infobox": {
                "caption": "旅行者（主角）",
                "series": "《原神》角色",
                "image": None,
                "rows": [
                    {"label": "首次登场", "value": "序章·第一幕「捕风的异乡人」"},
                    {"label": "创作者", "value": "米哈游 / HoYoverse"},
                    {"label": "配音（空）", "value": "鹿喑 / Zach Aguilar"},
                    {"label": "配音（荧）", "value": "宴宁 / Sarah Miller-Crews"},
                    {"label": "性别", "value": "男（空）/ 女（荧）"},
                    {"label": "重要他人", "value": "血亲、派蒙、温迪、钟离等"},
                    {"label": "命之座", "value": "旅人座（Viator）"},
                    {"label": "元素力", "value": "风/岩/雷/草/水/火"},
                    {"label": "武器类型", "value": "单手剑"},
                ],
            },
        },
        "main",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{S['creation']}",
        {
            "content": (
                "旅行者是《原神》叙事与玩法的双核心，串联各国主线与大量世界任务。"
                "设定上来自世界之外；因天理一方介入，血亲被带走，旅行者亦被封印，"
                "多年后于蒙德苏醒。[^1][^4]\n\n"
                "空与荧共享动作模组，拥有独立配音与部分剧情差分。[^5]"
            ),
        },
        "creation",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{S['voice']}",
        {
            "content": (
                "空华语配音鹿喑，荧为宴宁；日语堀江瞬/悠木碧，英语 Zach Aguilar / "
                "Sarah Miller-Crews。[^5][^6]\n\n"
                "金发、异域服饰与单耳耳坠为早期识别特征；"
                "随国家推进服装与元素特效持续更新。[^7]"
            ),
        },
        "voice",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{S['anime']}",
        {
            "content": (
                "**外部视频链接**\n\n"
                "[YouTube：《原神》动画短片—「未行之路」](https://www.youtube.com/watch?v=Zy9bbgMix6w)\n\n"
                "短片以空、荧与血亲的回忆为主线，配合 Aimer 演唱的主题曲，"
                "在 2024 年版本更新前后引发广泛讨论。[^9]"
            ),
            "infobox": {
                "caption": "未行之路",
                "series": "HOYO-MiX / Aimer",
                "image": None,
                "rows": [
                    {"label": "发行日期", "value": "2024年5月25日"},
                    {"label": "时长", "value": "2:30"},
                    {"label": "作曲", "value": "HOYO-MiX"},
                    {"label": "演唱", "value": "Aimer"},
                ],
            },
        },
        "anime",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{S['performance']}",
        {
            "content": (
                "主线中旅行者以寻找血亲为长期目标，短期协助各国化解危机。"
                "少言台词强化代入感，亦引发叙事参与度争议。[^8]"
            ),
        },
        "performance",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{S['story']}",
        {
            "content": (
                "主角与血亲为来自世界之外的双胞胎，见证多界毁灭与新生。"
                "抵达提瓦特后遭神祇阻拦，血亲被带走，旅行者被封印。[^18]\n\n"
                "苏醒后结识派蒙，卷入风魔龙、璃月、稻妻、须弥、枫丹、纳塔等国主线，"
                "每国通常解锁对应元素。[^19][^20]"
            ),
        },
        "story",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{S['gameplay']}",
        {
            "content": (
                "旅行者已可掌握风、岩、雷、草、水、火六种元素，切换元素参与战斗与解谜。[^27]\n\n"
                "评测多认为输出偏弱，但在部分配队仍有功能性；"
                "探索上元素技能与机关、神像强绑定。[^28][^3]"
            ),
        },
        "gameplay",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{S['reception']}",
        {
            "content": (
                "旅行者常见于宣传、周年与联动，是《原神》对外形象核心。"
                "评价集中在代入感、叙事参与度与强度三条线。[^28][^30]"
            ),
        },
        "reception",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{S['design']}",
        {
            "content": (
                "金发、轻盈体态与元素特效使其易识别。部分玩家认为服装相对朴素；"
                "亦有观点认为这是为玩家投射而保留的设计。[^32][^33]"
            ),
        },
        "design",
    )

    sec_char = post(
        f"/wiki/pages/{pid}/sections",
        {
            "parentSection": S["reception"],
            "title": "角色塑造",
            "afterSection": S["design"],
        },
        "add-角色塑造",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{sec_char}",
        {
            "content": (
                "旅行者的角色塑造长期处于「独立角色」与「玩家代入工具」之间："
                "剧情上其行动推动各国事件，但台词量偏少、情感表达多依赖玩家选择。"
                "部分主线（如须弥、枫丹）尝试赋予更强立场，社群反馈分化。[^36][^37]"
            ),
        },
        "角色塑造",
    )

    sec_play_exp = post(
        f"/wiki/pages/{pid}/sections",
        {
            "parentSection": S["reception"],
            "title": "玩法体验",
            "afterSection": sec_char,
        },
        "add-玩法体验",
    )

    patch(
        f"/wiki/pages/{pid}/sections/{sec_play_exp}",
        {
            "content": (
                "评论大多将旅行者评为偏弱可玩角色，但承认其在开荒、解谜与特定反应队中的价值。"
                "元素切换机制在探索期体验突出，深境螺旋等终局内容则常被建议替换为限定五星。[^27][^28]"
            ),
        },
        "玩法体验",
    )

    put(
        f"/wiki/pages/{pid}/footnotes",
        {
            "items": [
                {"id": "a", "text": "指代序章中天空岛相关空间，社群常类比为「监狱」式封闭结构"},
                {"id": "b", "text": "荧（Lumine）名字在部分资料中关联「光明」意象"},
                {"id": "c", "text": "派蒙作为引导者，其真实身份在剧情后期揭示，此处不展开"},
            ],
        },
        "footnotes",
    )

    put(
        f"/wiki/pages/{pid}/references",
        {
            "items": [
                {
                    "id": "1",
                    "text": "Ballestrasse, Michelle. Genshin Impact Developer Settles Aether & Lumine Traveler Debate. ScreenRant. 2021-05-30.",
                    "url": "/details/article/5be0ffe9306d4b9f235ef0acbf9709d3",
                    "entityType": "article",
                    "entityUuid": "5be0ffe9306d4b9f235ef0acbf9709d3",
                },
                {
                    "id": "2",
                    "text": "HoYoverse. Genshin Impact Official Traveler Overview. 2023.",
                    "url": "https://example.com/ref/2",
                },
                {
                    "id": "3",
                    "text": "Genshin Impact Wiki. Traveler/Combat and Exploration. community doc.",
                    "url": "https://example.com/ref/3",
                },
                {
                    "id": "4",
                    "text": "miHoYo. Story Archive: Prologue. In-game material summary.",
                    "url": "https://example.com/ref/4",
                },
                {
                    "id": "5",
                    "text": "Castania, Gabrielle. Every Character And Their Voice Actor In Genshin Impact. The Gamer. 2026-02-27.",
                    "url": "https://example.com/source/5",
                },
                {
                    "id": "6",
                    "text": "Behind the Voice: Genshin Impact Traveler EN cast interview. 2022.",
                    "url": "https://example.com/ref/6",
                },
                {
                    "id": "7",
                    "text": "Character design analysis: Traveler visual evolution patch notes. 2024.",
                    "url": "https://example.com/ref/7",
                },
                {
                    "id": "8",
                    "text": "Narrative design in open-world RPGs: silent protagonist case study. 2021.",
                    "url": "https://example.com/ref/8",
                },
                {
                    "id": "9",
                    "text": "「未行之路」动画短片发布报道. 2024-05-25.",
                    "url": "https://www.youtube.com/watch?v=Zy9bbgMix6w",
                },
                {
                    "id": "18",
                    "text": "Archon Quest Chapter Prologue: Act I — summary of twin separation scene.",
                    "url": "https://example.com/ref/18",
                },
                {
                    "id": "19",
                    "text": "Regional Archon Quest timeline through Sumeru. fan-compiled chronology.",
                    "url": "https://example.com/ref/19",
                },
                {
                    "id": "20",
                    "text": "Fontaine & Natlan main story traveler role overview. 2025.",
                    "url": "https://example.com/ref/20",
                },
                {
                    "id": "27",
                    "text": "Traveler elemental forms tier discussion. community benchmark 2026.",
                    "url": "https://example.com/ref/27",
                },
                {
                    "id": "28",
                    "text": "Meta review: Traveler usage rate in Spiral Abyss. 2025-Q4.",
                    "url": "https://example.com/ref/28",
                },
                {
                    "id": "30",
                    "text": "Marketing presence of Traveler in anniversary key visuals. press kit.",
                    "url": "https://example.com/ref/30",
                },
                {
                    "id": "32",
                    "text": "Community poll: satisfaction with traveler outfit variants. 2024.",
                    "url": "https://example.com/ref/32",
                },
                {
                    "id": "33",
                    "text": "Art director interview excerpt on protagonist design constraints. 2023.",
                    "url": "https://example.com/ref/33",
                },
                {
                    "id": "36",
                    "text": "Writing the mute protagonist: affordances and limits. game writing journal.",
                    "url": "https://example.com/ref/36",
                },
                {
                    "id": "37",
                    "text": "Player survey: emotional attachment to Lumine vs Aether routes. 2025.",
                    "url": "https://example.com/ref/37",
                },
            ],
        },
        "references",
    )

    patch(
        f"/wiki/pages/{pid}/meta",
        {
            "title": "旅行者 (原神)",
            "sourceNote": "知识库条目 · 前端联调种子（已扩充）",
            "categories": [
                "原神角色",
                "沉默的主角",
                "虚构双胞胎",
                "开放世界RPG",
                "前端联调",
                "米哈游",
                "主角设计",
                "2024年游戏角色",
            ],
            "status": "published",
            "changeSummary": "扩充联调样例内容",
        },
        "meta",
    )

    final = api("GET", f"/wiki/pages/by-slug/{SLUG}")
    print(f"final revision={final['data']['revision']}")
    print(f"citationHealth={json.dumps(final['data']['citationHealth'], ensure_ascii=False)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
