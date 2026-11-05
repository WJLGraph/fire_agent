"""
鉴权覆盖静态检查 —— 「漏写一个 Depends」从此不可能悄悄发生

为什么要它：本轮安全复核发现的两个 P0（/admin/* 只验登录不验管理员、
5 个业务端点完全无鉴权）本质是同一个错误 —— 忘了挂依赖。靠人审只能保证
当下不漏；把「每个端点都必须显式表态」变成可机器校验的不变量，才会持续不漏。

做法：遍历 app/api/v1/routes/*.py 里每个 APIRouter 的 APIRoute，解析其 FastAPI
依赖树（递归，含函数级 Depends 与装饰器 dependencies），再叠上 router 级
dependencies（admin 路由就是靠这一层收口的）。
不扫描 app.routes：FastAPI 0.141 把 include_router 延后成 _IncludedRouter，
导入期拿不到最终 path，依赖信息也随之不可见；改用模块级 router 对象 +
openapi 的操作总数做交叉校验，既稳定又能发现「有路由文件没被注册」。

公开端点必须在函数 docstring 里写 `AUTH: PUBLIC` 并说明理由，否则判为不合规 ——
「表态」这件事本身就是检查的目的。

用法：
    python scripts/check_auth_coverage.py            # 本地查看
    python scripts/check_auth_coverage.py --quiet    # CI 用，仅失败时输出并非零退出
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402

ROUTES_DIR = ROOT / "app" / "api" / "v1" / "routes"

#: 视为「已鉴权」的依赖函数名。resolve_user 是 Header 与 SSE query 共用的入口；
#: get_stream_user 是它在 SSE 上的包装（EventSource 不能带自定义头，故多一条 query 通道）。
AUTH_CALLS = {"get_current_user", "get_current_admin", "resolve_user", "get_stream_user"}

#: 登录/注册本身不可能带 token；健康探针给宝塔监控与容器编排用。
BUILTIN_PUBLIC = {"login", "register", "health", "root"}

PUBLIC_MARKER = "AUTH: PUBLIC"


def _dep_names(dependant) -> set[str]:
    """深度遍历 FastAPI 依赖树，收集所有被调用的依赖函数名"""
    names: set[str] = set()
    stack = [dependant]
    while stack:
        cur = stack.pop()
        call = getattr(cur, "call", None)
        if call is not None:
            names.add(getattr(call, "__name__", str(call)))
        stack.extend(getattr(cur, "dependencies", []) or [])
    return names


def _router_level_calls(router: APIRouter) -> set[str]:
    """APIRouter(dependencies=[...]) 上的全局依赖

    注意：这层依赖是在 include_router 时才并入每条路由的 dependant 的，
    直接读 route.dependant 看不到，必须单独取 router.dependencies。
    """
    names = set()
    for dep in router.dependencies or []:
        call = getattr(dep, "dependency", None) or getattr(dep, "call", None)
        if call is not None:
            names.add(getattr(call, "__name__", str(call)))
    return names


def _iter_module_routers():
    """(来源标识, router 级依赖名集合, APIRoute 列表)"""
    for module_path in sorted(ROUTES_DIR.glob("*.py")):
        module = importlib.import_module(f"app.api.v1.routes.{module_path.stem}")
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            continue  # __init__.py 等无 router 的文件
        yield module_path.name, _router_level_calls(router), [
            r for r in router.routes if isinstance(r, APIRoute)
        ]


def _app_level_routes() -> list[APIRoute]:
    """直接挂在 @app.get / @app.post 上的端点（main.py 的 / 与 /health）。

    它们不在 routes/ 目录里，但同样必须纳入鉴权检查，否则「根路径忘了加鉴权」
    是这套检查的盲区。FastAPI 0.141 的 include_router 结果是不可解析的
    _IncludedRouter，因此这里只取真正的 APIRoute 实例。
    """
    from app.main import app

    return [r for r in app.routes if isinstance(r, APIRoute)]


def collect() -> tuple[list[str], int]:
    """返回 (不合规端点列表, 扫描到的 HTTP 操作数)"""
    violations: list[str] = []
    total = 0

    groups = [
        (name, router_calls, routes) for name, router_calls, routes in _iter_module_routers()
    ]
    groups.append(("main.py", set(), _app_level_routes()))

    for source, router_calls, routes in groups:
        for route in routes:
            methods = route.methods - {"HEAD", "OPTIONS"}
            total += len(methods)
            name = route.endpoint.__name__
            if name in BUILTIN_PUBLIC:
                continue
            if router_calls & AUTH_CALLS:
                continue
            if _dep_names(route.dependant) & AUTH_CALLS:
                continue
            doc = getattr(route.endpoint, "__doc__", "") or ""
            if PUBLIC_MARKER in doc:
                continue
            line = getattr(getattr(route.dependant, "call", None), "__code__", None)
            loc = f"{source}:{line.co_firstlineno:<5}" if line else source
            label = ",".join(sorted(methods))
            violations.append(f"{loc} {label:18} {route.path:50} ({name})")
    return violations, total


def _openapi_operation_count() -> int:
    from app.main import app

    spec = app.openapi()
    return sum(len(v) for v in spec.get("paths", {}).values())


def main() -> int:
    parser = argparse.ArgumentParser(description="检查每条 API 路由是否显式声明了鉴权口径")
    parser.add_argument("--quiet", action="store_true", help="只在失败时输出，供 CI 使用")
    args = parser.parse_args()

    violations, total = collect()

    # 交叉校验：扫到的端点数应与 OpenAPI 的操作数一致。
    # 对不上说明有路由文件没导出名为 router 的 APIRouter，或压根没注册进 app。
    registered = _openapi_operation_count()
    if registered != total:
        print(
            f"[AUTH-CHECK] 自检失配：扫描到 {total} 条路由，但 OpenAPI 暴露 {registered} 个操作。"
            "\n  请先确认新增的 routes 文件是否以 `router = APIRouter()` 命名并注册进 app/main.py。"
        )
        return 1

    if violations:
        print(f"[AUTH-CHECK] 发现 {len(violations)} 个未声明鉴权口径的端点：")
        for v in violations:
            print("  -", v)
        print(
            "\n修复二选一：\n"
            "  1) 函数签名加 current: User = Depends(get_current_user)"
            "（管理功能用 get_current_admin）\n"
            f"  2) 确需匿名：在 docstring 写一行 '{PUBLIC_MARKER} —— <为什么公开>'\n"
            "     参考 app/api/v1/routes/dashboard.py 的 /summary（门户页未登录取数）"
        )
        return 1

    if not args.quiet:
        print(f"[AUTH-CHECK] OK：{total} 条路由全部显式声明了鉴权口径（与 OpenAPI 操作数一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
