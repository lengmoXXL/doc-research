#!/usr/bin/env python3
"""项目初始化：交互式填写 .env 凭据。"""

import getpass
import sys
from pathlib import Path

ENV_KEYS = ("ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET")


def read_secret(key: str) -> str:
    if sys.stdin.isatty():
        return getpass.getpass(f"{key}: ")
    print(f"{key}: ", end="", flush=True)
    return sys.stdin.readline().strip()


def write_env(env_path: Path, values: dict) -> None:
    # 已存在的 .env 只更新对应键，保留其它配置
    lines = (
        env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    )
    remaining = dict(values)
    output = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in remaining.items())
    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    env_path.chmod(0o600)


def cmd_env(args) -> int:
    env_path = Path(args.dir) / ".env"
    values = {}
    for key in ENV_KEYS:
        value = read_secret(key)
        if not value:
            print(f"{key} 不能为空", file=sys.stderr)
            return 1
        values[key] = value
    write_env(env_path, values)
    print(f"已写入 {env_path}（权限 600）")
    return 0


def cmd_check(args) -> int:
    project = Path(args.dir).resolve()
    problems = []

    values = {}
    env_path = project / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    for key in ENV_KEYS:
        if not values.get(key):
            problems.append(f".env 缺少 {key}（运行 doc-research env 填写）")

    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print("项目检查通过。")
    return 0


def cmd_init(args) -> int:
    if rc := cmd_env(args):
        return rc
    print("初始化完成。")
    return 0
