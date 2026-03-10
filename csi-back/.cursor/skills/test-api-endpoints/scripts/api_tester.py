#!/usr/bin/env python3
"""API 接口测试工具

用法：
  # 运行测试计划文件
  python api_tester.py plan <test_plan.json> [--verbose]

  # 单接口测试
  python api_tester.py request --url <base_url> --path <path> --method <GET|POST|PUT|DELETE>
    [--body '{}'] [--query '{}'] [--headers '{}']
    [--expected-code 0] [--expected-status-code 200] [--expected-data key=value ...]
"""

import argparse
import json
import sys
import uuid
from typing import Any

import requests


def dotpath_get(obj: Any, path: str) -> Any:
    """按点路径从对象中提取值，如 data.id"""
    parts = path.split(".")
    for part in parts:
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def interpolate(value: Any, variables: dict) -> Any:
    """将字符串中的 {variable} 替换为已存储的变量值"""
    if isinstance(value, str):
        for k, v in variables.items():
            value = value.replace(f"{{{k}}}", str(v))
        return value
    elif isinstance(value, dict):
        return {k: interpolate(v, variables) for k, v in value.items()}
    elif isinstance(value, list):
        return [interpolate(item, variables) for item in value]
    return value


def make_request(
    session: requests.Session,
    base_url: str,
    step: dict,
    variables: dict,
) -> dict:
    """执行单个请求步骤，返回结果字典"""
    method = step.get("method", "GET").upper()
    path = interpolate(step.get("path", ""), variables)
    url = base_url.rstrip("/") + path
    body = interpolate(step.get("body"), variables) if step.get("body") is not None else None
    query = interpolate(step.get("query", {}), variables) or None
    extra_headers = step.get("headers", {})

    try:
        response = session.request(
            method=method,
            url=url,
            json=body,
            params=query,
            headers=extra_headers,
            timeout=30,
        )
        resp_data = response.json()
    except Exception as e:
        return {"ok": False, "error": str(e), "status_code": None, "data": None, "url": url, "method": method}

    return {"ok": True, "status_code": response.status_code, "data": resp_data, "error": None, "url": url, "method": method}


def validate_response(result: dict, expected: dict) -> list:
    """校验响应，返回错误描述列表（空列表表示通过）"""
    errors = []
    if not result["ok"]:
        errors.append(f"请求异常: {result['error']}")
        return errors

    data = result["data"]

    if "code" in expected:
        actual_code = data.get("code") if isinstance(data, dict) else None
        if actual_code != expected["code"]:
            errors.append(f"业务响应码不匹配: 期望 {expected['code']}，实际 {actual_code}（message: {data.get('message') if isinstance(data, dict) else '-'}）")

    if "code_in" in expected:
        actual_code = data.get("code") if isinstance(data, dict) else None
        if actual_code not in expected["code_in"]:
            errors.append(f"业务响应码不在允许范围: 期望 {expected['code_in']} 之一，实际 {actual_code}（message: {data.get('message') if isinstance(data, dict) else '-'}）")

    if "status_code" in expected:
        if result["status_code"] != expected["status_code"]:
            errors.append(f"HTTP 状态码不匹配: 期望 {expected['status_code']}，实际 {result['status_code']}")

    if "data" in expected and isinstance(expected["data"], dict):
        for key, val in expected["data"].items():
            actual = dotpath_get(data, f"data.{key}") if isinstance(data, dict) else None
            if actual != val:
                errors.append(f"字段 data.{key} 不匹配: 期望 {val!r}，实际 {actual!r}")

    return errors


def print_step_result(name: str, result: dict, errors: list, verbose: bool = False):
    status = "PASS 通过" if not errors else "FAIL 失败"
    print(f"  [{status}] {name}")
    print(f"          {result.get('method', '')} {result.get('url', '')}")
    if errors:
        for err in errors:
            print(f"          -> {err}")
    if verbose:
        print(f"          响应: {json.dumps(result.get('data'), ensure_ascii=False, indent=2)}")


def run_plan(plan_path: str, verbose: bool = False) -> int:
    """运行测试计划文件，返回失败步骤数"""
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)

    base_url = plan.get("base_url", "http://localhost:8080/api/v1")
    global_headers = plan.get("headers", {})
    variables: dict = {"uuid": str(uuid.uuid4())[:8]}
    total = 0
    failed = 0

    session = requests.Session()
    if global_headers:
        session.headers.update(global_headers)

    def run_steps(steps: list, phase_name: str) -> tuple[int, int]:
        """执行一组步骤，返回 (total, failed)"""
        if not steps:
            return 0, 0
        phase_total = 0
        phase_failed = 0
        print(f"\n【{phase_name}】")
        for step in steps:
            name = step.get("name", "未命名")
            result = make_request(session, base_url, step, variables)
            expected = step.get("expected", {"code": 0})
            errors = validate_response(result, expected)
            print_step_result(name, result, errors, verbose)
            phase_total += 1
            if errors:
                phase_failed += 1
            elif step.get("extract"):
                for var_name, path in step["extract"].items():
                    val = dotpath_get(result["data"], path)
                    variables[var_name] = val
        return phase_total, phase_failed

    def run_teardown(steps: list):
        """执行恢复现场步骤，失败仅提示，不计入测试统计"""
        if not steps:
            return
        print(f"\n【Teardown 恢复现场】")
        for step in steps:
            name = step.get("name", "未命名")
            result = make_request(session, base_url, step, variables)
            expected = step.get("expected", {"code": 0})
            errors = validate_response(result, expected)
            if errors:
                print(f"  [WARN 警告] {name}")
                print(f"          {result.get('method', '')} {result.get('url', '')}")
                for err in errors:
                    print(f"          -> {err}")
            else:
                print(f"  [OK 完成] {name}")
                print(f"          {result.get('method', '')} {result.get('url', '')}")
                if step.get("extract"):
                    for var_name, path in step["extract"].items():
                        val = dotpath_get(result["data"], path)
                        variables[var_name] = val
            if verbose:
                print(f"          响应: {json.dumps(result.get('data'), ensure_ascii=False, indent=2)}")

    step_total, step_failed = run_steps(plan.get("tests", []), "Test 执行测试")
    total += step_total
    failed += step_failed

    run_teardown(plan.get("teardown", []))

    print(f"\n{'=' * 48}")
    print(f"测试完成：共 {total} 项，通过 {total - failed} 项，失败 {failed} 项")
    return failed


def run_single(args) -> int:
    """单接口请求测试"""
    url = args.url.rstrip("/") + args.path
    headers = json.loads(args.headers) if args.headers else {}
    body = json.loads(args.body) if args.body else None
    query = json.loads(args.query) if args.query else None

    print(f"\n请求: {args.method.upper()} {url}")

    try:
        response = requests.request(
            method=args.method.upper(),
            url=url,
            json=body,
            params=query,
            headers=headers,
            timeout=30,
        )
        data = response.json()
    except Exception as e:
        print(f"请求失败: {e}")
        return 1

    print(f"HTTP 状态码: {response.status_code}")
    print(f"响应内容:\n{json.dumps(data, ensure_ascii=False, indent=2)}")

    errors = []

    if args.expected_code is not None:
        actual_code = data.get("code") if isinstance(data, dict) else None
        if actual_code != args.expected_code:
            errors.append(f"业务响应码不匹配: 期望 {args.expected_code}，实际 {actual_code}（message: {data.get('message') if isinstance(data, dict) else '-'}）")

    if args.expected_status_code is not None:
        if response.status_code != args.expected_status_code:
            errors.append(f"HTTP 状态码不匹配: 期望 {args.expected_status_code}，实际 {response.status_code}")

    if args.expected_data:
        for kv in args.expected_data:
            if "=" not in kv:
                print(f"[警告] --expected-data 格式无效（应为 key=value）: {kv}")
                continue
            key, _, expected_val = kv.partition("=")
            actual = dotpath_get(data, f"data.{key}") if isinstance(data, dict) else None
            actual_str = str(actual) if actual is not None else None
            if actual_str != expected_val:
                errors.append(f"字段 data.{key} 不匹配: 期望 {expected_val!r}，实际 {actual!r}")

    if errors:
        print()
        for err in errors:
            print(f"[FAIL] {err}")
        return 1

    if args.expected_code is not None or args.expected_status_code is not None or args.expected_data:
        print("\n[PASS] 验证通过")

    return 0


def main():
    parser = argparse.ArgumentParser(description="API 接口测试工具")
    subparsers = parser.add_subparsers(dest="mode")

    plan_parser = subparsers.add_parser("plan", help="运行测试计划 JSON 文件")
    plan_parser.add_argument("plan_file", help="测试计划 JSON 文件路径")
    plan_parser.add_argument("--verbose", "-v", action="store_true", help="打印完整响应内容")

    req_parser = subparsers.add_parser("request", help="单接口测试")
    req_parser.add_argument("--url", required=True, help="Base URL，如 http://localhost:8080/api/v1")
    req_parser.add_argument("--path", required=True, help="接口路径，如 /action/resource")
    req_parser.add_argument("--method", default="GET", help="HTTP 方法（默认 GET）")
    req_parser.add_argument("--body", help="请求体 JSON 字符串")
    req_parser.add_argument("--query", help="Query 参数 JSON 字符串")
    req_parser.add_argument("--headers", help="额外请求头 JSON 字符串")
    req_parser.add_argument("--expected-code", type=int, dest="expected_code", help="期望的业务响应码")
    req_parser.add_argument("--expected-status-code", type=int, dest="expected_status_code", help="期望的 HTTP 状态码")
    req_parser.add_argument("--expected-data", action="append", dest="expected_data", metavar="key=value", help="验证响应 data 中的字段（可多次使用）")

    args = parser.parse_args()

    if args.mode == "plan":
        failed = run_plan(args.plan_file, getattr(args, "verbose", False))
        sys.exit(1 if failed > 0 else 0)
    elif args.mode == "request":
        sys.exit(run_single(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
