#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deepseek-eyes 一键安装器（轻量版）

做四件事：
  1. 把 see.py 装到 ~/.deepseek-eyes/
  2. 让你配置一个或多个多模态后端（每个后端各带自己的 key / 接口 / 模型），
     存进 ~/.deepseek-eyes/config.json
  3. 把技能说明书装进各个 agent 软件（WorkBuddy / Claude Code / Codex / Trae / zcode 等）
  4. 跑一次自检，确认眼睛真能睁开

所有后端都走 OpenAI 兼容协议：GPT-5.6 Luna、GPT-4o、Qwen-VL，或任意 OpenAI 兼容中转站。
想用 Gemini / Claude，把 base_url 填成它们对应的 OpenAI 兼容地址即可。

用法：
  python install.py                                  # 交互式安装，可添加多个后端，推荐
  python install.py --all                            # 装到所有支持的 agent，不管有没有检测到
  python install.py --backend luna --api-key sk-xxx --yes
  python install.py --backend gpt4o --base-url https://openrouter.ai/api/v1 --api-key sk-xxx --yes
  python install.py --targets workbuddy,claude
  python install.py --uninstall                      # 卸载
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HOME = os.path.normpath(os.path.expanduser("~"))
INSTALL_DIR = os.path.join(HOME, ".deepseek-eyes")
CONFIG_PATH = os.path.join(INSTALL_DIR, "config.json")
SEE_DST = os.path.join(INSTALL_DIR, "see.py")

HERE = os.path.dirname(os.path.abspath(__file__))
SEE_SRC = os.path.join(HERE, "scripts", "see.py")
SKILL_SRC = os.path.join(HERE, "SKILL.md")

SKILL_NAME = "deepseek-eyes"
MARK_BEGIN = "<!-- deepseek-eyes:begin 自动生成，勿手工修改本段 -->"
MARK_END = "<!-- deepseek-eyes:end -->"

OFFICIAL_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL_OPENAI = "gpt-5.6-luna"

# Luna 官方降价后公开单价（美元/百万 token），仅当模型正好是 gpt-5.6-luna 时预填
LUNA_PRICE = {"price_in": 0.20, "price_cached_in": 0.02, "price_out": 1.20}

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ------------------------------------------------------------ 安装目标定义
# kind = "skill" : 目录式技能，放一份完整 SKILL.md
# kind = "rules" : 单个规则文件，追加一段用标记包裹的引导文字

TARGETS = [
    {
        "id": "workbuddy",
        "name": "WorkBuddy",
        "kind": "skill",
        "probe": os.path.join(HOME, ".workbuddy"),
        "path": os.path.join(HOME, ".workbuddy", "skills", SKILL_NAME, "SKILL.md"),
    },
    {
        "id": "claude",
        "name": "Claude Code",
        "kind": "skill",
        "probe": os.path.join(HOME, ".claude"),
        "path": os.path.join(HOME, ".claude", "skills", SKILL_NAME, "SKILL.md"),
    },
    {
        "id": "codex",
        "name": "Codex",
        "kind": "rules",
        "probe": os.path.join(HOME, ".codex"),
        "path": os.path.join(HOME, ".codex", "AGENTS.md"),
    },
    {
        "id": "trae",
        "name": "Trae",
        "kind": "rules",
        "probe": os.path.join(HOME, ".trae"),
        "path": os.path.join(HOME, ".trae", "rules", "user_rules.md"),
    },
    {
        "id": "zcode",
        "name": "ZCode",
        "kind": "rules",
        "probe": os.path.join(HOME, ".zcode"),
        "path": os.path.join(HOME, ".zcode", "AGENTS.md"),
    },
    {
        "id": "agents",
        "name": "通用 .agents 约定（其他支持 AGENTS.md 的工具）",
        "kind": "rules",
        "probe": os.path.join(HOME, ".agents"),
        "path": os.path.join(HOME, ".agents", "AGENTS.md"),
    },
]


# ------------------------------------------------------------ 小工具


def say(msg=""):
    print(msg, flush=True)


def ask(prompt, default=""):
    if not sys.stdin or not sys.stdin.isatty():
        return default
    try:
        v = input(prompt).strip()
    except EOFError:
        return default
    return v or default


def ask_yes(prompt, default=True):
    if not sys.stdin or not sys.stdin.isatty():
        return default
    tip = "[Y/n]" if default else "[y/N]"
    v = ask("%s %s " % (prompt, tip), "").lower()
    if not v:
        return default
    return v in ("y", "yes", "是", "好", "1")


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def see_cmd():
    """agent 实际要敲的命令，路径写死成绝对路径，避免环境差异。"""
    py = sys.executable or "python"
    return '"%s" "%s"' % (py, SEE_DST)


def _mask(key):
    if len(key) > 12:
        return key[:6] + "..." + key[-4:]
    return "(还没填)" if not key else "***"


# ------------------------------------------------------------ 规则片段


def rules_snippet():
    return """%s
## 看图能力（deepseek-eyes）

当前模型看不见图像。凡是涉及图片、截图、设计稿、报错截图、图表、扫描件的任务，
必须先执行下面的命令把图转成文字，再基于返回的文字继续工作。
**禁止根据文件名或上下文猜测图片内容——没调脚本就等于没看见。**

```bash
%s <图片路径或网址> [-q "具体问题"] [--backend <后端名>]
```

不写 -q 就做通用详细描述；写了 -q 就只回答那个具体问题。
后端：配置文件里可以写多个多模态后端（各用各的 key，都走 OpenAI 兼容协议），
不写 --backend 时用 default_backend；要换模型就加 --backend <名字>。

其他参数：`--json` 结构化输出｜`--max-side 2048` 图太糊时提高清晰度｜`--check` 自检配置与网络

省钱守则：一次把要问的都写进 -q 问全，不要反复调；不需要看图的任务不要调这个脚本。

完整说明书：%s
%s""" % (
        MARK_BEGIN,
        see_cmd(),
        os.path.join(INSTALL_DIR, "SKILL.md"),
        MARK_END,
    )


def upsert_block(path, block):
    """把标记块写进文件：已有就替换，没有就追加。不动用户其他内容。"""
    old = ""
    if os.path.isfile(path):
        old = read_text(path)
    pattern = re.compile(
        re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END), re.S
    )
    if pattern.search(old):
        new = pattern.sub(block, old)
        action = "已更新"
    else:
        sep = "" if not old else ("\n\n" if not old.endswith("\n") else "\n")
        new = old + sep + block + "\n"
        action = "已追加"
    write_text(path, new)
    return action


def remove_block(path):
    if not os.path.isfile(path):
        return False
    old = read_text(path)
    pattern = re.compile(
        re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END) + r"\n?", re.S
    )
    if not pattern.search(old):
        return False
    write_text(path, pattern.sub("", old).rstrip() + "\n")
    return True


# ------------------------------------------------------------ 配置读写


def load_existing_backends():
    """读旧配置，返回 (backends 字典, default_backend)。兼容旧版顶层写法。"""
    backends = {}
    default = ""
    if not os.path.isfile(CONFIG_PATH):
        return backends, default
    try:
        old = json.load(open(CONFIG_PATH, "r", encoding="utf-8"))
    except Exception:
        return backends, default
    if not isinstance(old, dict):
        return backends, default

    if "backends" not in old:
        # 旧版：顶层 api_key / base_url / model
        if old.get("api_key") or old.get("base_url") or old.get("model") or old.get("price_in"):
            b = {
                "api_key": old.get("api_key", ""),
                "base_url": old.get("base_url", "") or OFFICIAL_BASE,
                "model": old.get("model", "") or DEFAULT_MODEL_OPENAI,
            }
            if old.get("price_in") is not None:
                b["price_in"] = old.get("price_in")
            if old.get("price_cached_in") is not None:
                b["price_cached_in"] = old.get("price_cached_in")
            if old.get("price_out") is not None:
                b["price_out"] = old.get("price_out")
            backends["luna"] = b
            default = "luna"
        return backends, default

    for name, b in (old.get("backends") or {}).items():
        if not isinstance(b, dict):
            continue
        b = dict(b)
        b.pop("provider", None)  # 轻量版只用 OpenAI 兼容协议
        b.setdefault("base_url", OFFICIAL_BASE)
        b.setdefault("model", DEFAULT_MODEL_OPENAI)
        backends[name] = b
    default = old.get("default_backend") or (next(iter(backends)) if backends else "")
    return backends, default


def normalize_openai_base(base_url):
    base_url = (base_url or OFFICIAL_BASE).rstrip("/")
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    if not base_url.endswith("/v1") and "openai.com" in base_url:
        base_url = base_url + "/v1"
    return base_url


# ------------------------------------------------------------ 各步骤


def step_copy_script():
    if not os.path.isfile(SEE_SRC):
        say("找不到核心脚本：%s" % SEE_SRC)
        say("请在解压后的 deepseek-eyes 目录里运行本安装器。")
        sys.exit(1)
    os.makedirs(INSTALL_DIR, exist_ok=True)
    shutil.copy2(SEE_SRC, SEE_DST)
    if os.path.isfile(SKILL_SRC):
        write_text(
            os.path.join(INSTALL_DIR, "SKILL.md"),
            read_text(SKILL_SRC).replace("{{SEE_CMD}}", see_cmd()),
        )
    say("核心脚本已装到：%s" % SEE_DST)


def _add_one_backend(name, args, backends):
    """填好一个后端（OpenAI 兼容协议），写进 backends。"""
    b = {"api_key": ""}
    base_url = args.base_url
    model = args.model

    non_interactive = args.api_key and args.yes and not sys.stdin.isatty()
    if not non_interactive:
        say("  （OpenAI 兼容协议：Luna / GPT-4o / Qwen-VL 都走这套；中转站也走这套）")
        if not base_url:
            say("  接口地址：1) OpenAI 官方 %s  2) 中转站/聚合站（如 https://openrouter.ai/api/v1）" % OFFICIAL_BASE)
            c = ask("  选 1 / 2，或直接粘贴地址（回车用官方）：", "1")
            if c == "1":
                base_url = OFFICIAL_BASE
            elif c == "2":
                base_url = ask("  粘贴中转站地址：", OFFICIAL_BASE)
            elif c:
                base_url = c
            else:
                base_url = OFFICIAL_BASE
        b["base_url"] = normalize_openai_base(base_url)
        mm = model or ask("  模型名（官方默认 %s；中转站可能不同）：" % DEFAULT_MODEL_OPENAI, DEFAULT_MODEL_OPENAI)
        b["model"] = mm
        if mm == DEFAULT_MODEL_OPENAI:
            b.update(LUNA_PRICE)
    else:
        b["base_url"] = normalize_openai_base(base_url or OFFICIAL_BASE)
        b["model"] = model or DEFAULT_MODEL_OPENAI
        if (model or DEFAULT_MODEL_OPENAI) == DEFAULT_MODEL_OPENAI:
            b.update(LUNA_PRICE)

    if args.api_key:
        b["api_key"] = args.api_key
    else:
        b["api_key"] = ask("  粘贴 %s 的 API key：" % name, "")
    backends[name] = b
    say("  已记录后端 %s（模型 %s）" % (name, b["model"]))
    return b


def step_config(args):
    backends, default = load_existing_backends()

    non_interactive = args.api_key or (args.yes and not (sys.stdin and sys.stdin.isatty()))
    if non_interactive:
        name = args.backend or "luna"
        _add_one_backend(name, args, backends)
        default = default or name
    else:
        say()
        say("配置多模态后端（可以接多个，各用各的 key，都走 OpenAI 兼容协议）")
        idx = 0
        while True:
            idx += 1
            if idx == 1:
                name = ask("第一个后端起个名字（比如 luna / gpt4o / qwen，回车用 luna）：", "luna")
            else:
                name = ask("下一个后端起个名字（回车结束）：", "")
                if not name:
                    break
            if name in backends and not ask_yes("  %s 已存在，覆盖它吗？" % name, True):
                continue
            _add_one_backend(name, args, backends)
            if not ask_yes("还要再加一个后端吗？", False):
                break
        if not backends:
            say("一个后端都没配，退出。")
            sys.exit(1)
        if default in backends:
            chosen = default
        else:
            first = next(iter(backends))
            chosen = ask("默认用哪个后端（回车用第一个 %s）：" % first, first)
            if chosen not in backends:
                chosen = first
        default = chosen

    cfg = {
        "usd_to_cny": 7.2,
        "max_side": 1536,
        "default_backend": default,
        "backends": backends,
    }
    write_text(CONFIG_PATH, json.dumps(cfg, ensure_ascii=False, indent=2))
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except Exception:
        pass
    say()
    say("配置已存到：%s" % CONFIG_PATH)
    for n, b in backends.items():
        mark = " ← 默认" if n == default else ""
        say("  · %s %s  key=%s%s" % (n, b.get("model", "?"), _mask(b.get("api_key", "")), mark))
    return cfg


def step_install_targets(args):
    tpl = read_text(SKILL_SRC).replace("{{SEE_CMD}}", see_cmd())
    snippet = rules_snippet()

    if args.targets:
        wanted = set(t.strip() for t in args.targets.split(",") if t.strip())
        chosen = [t for t in TARGETS if t["id"] in wanted]
        unknown = wanted - set(t["id"] for t in TARGETS)
        if unknown:
            say("不认识这些目标：%s" % ", ".join(sorted(unknown)))
    elif args.all:
        chosen = list(TARGETS)
    else:
        detected = [t for t in TARGETS if os.path.isdir(t["probe"])]
        missing = [t for t in TARGETS if t not in detected]
        say()
        say("第三步：装到哪些 agent 软件")
        if detected:
            say("  检测到已安装：%s" % "、".join(t["name"] for t in detected))
        else:
            say("  没检测到任何已知 agent 的配置目录。")
        chosen = list(detected)
        if missing:
            say("  没检测到：%s" % "、".join(t["name"] for t in missing))
            if ask_yes("  要不要连这些也一起装上（以后装了软件就直接能用）？", True):
                chosen = list(TARGETS)

    if not chosen:
        say("  没有选中任何目标，跳过。")
        return []

    say()
    results = []
    for t in chosen:
        try:
            if t["kind"] == "skill":
                write_text(t["path"], tpl)
                results.append((t["name"], t["path"], "技能已写入"))
            else:
                action = upsert_block(t["path"], snippet)
                results.append((t["name"], t["path"], action + "规则段"))
        except Exception as e:
            results.append((t["name"], t["path"], "失败：%s" % e))

    for name, path, action in results:
        say("  [%s] %s → %s" % (action, name, path))
    return results


def step_deps(args):
    have_pil = _has("PIL")
    if have_pil:
        say()
        say("可选依赖已具备（Pillow，上传前自动压缩大图）。")
        return

    say()
    say("第四步：可选依赖")
    say("  Pillow —— 上传前把大图压小，省钱又快。没有也能用，只是贵一点。")

    do_install = args.deps
    if not do_install and not args.yes:
        do_install = ask_yes("  现在自动装上吗？", True)
    if not do_install:
        say('  跳过。以后想装就执行： "%s" -m pip install pillow' % sys.executable)
        return

    say("  正在安装：pillow")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pillow"], check=True)
        say("  装好了。")
    except Exception as e:
        say("  自动安装失败（%s）。手工执行： \"%s\" -m pip install pillow" % (e, sys.executable))


def _has(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def step_check(cfg):
    say()
    say("第五步：自检")
    say("-" * 52)
    try:
        subprocess.run([sys.executable, SEE_DST, "--check"], check=False)
    except Exception as e:
        say("自检没跑起来：%s" % e)


def do_uninstall():
    say("卸载 deepseek-eyes")
    say("-" * 52)
    for t in TARGETS:
        if t["kind"] == "skill":
            d = os.path.dirname(t["path"])
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
                if os.path.isdir(d):
                    say("  删不掉，请手动删除这个文件夹：%s" % d)
                else:
                    say("  已删除 %s" % d)
        else:
            if remove_block(t["path"]):
                say("  已从 %s 移除规则段" % t["path"])
    say()
    say("核心脚本和配置保留在 %s" % INSTALL_DIR)
    say("（里面有你的 API key，确认不用了再自己删这个文件夹）")


def main():
    p = argparse.ArgumentParser(description="deepseek-eyes 一键安装器")
    p.add_argument("--api-key", default="", help="后端 API key（配合 --backend 使用）")
    p.add_argument("--base-url", default="", help="OpenAI 兼容接口地址，一般带 /v1")
    p.add_argument("--model", default="", help="模型名")
    p.add_argument("--backend", default="", help="后端名字（默认 luna），用于新增/覆盖某个后端")
    p.add_argument("--targets", default="", help="只装指定目标，逗号分隔：%s" % ",".join(t["id"] for t in TARGETS))
    p.add_argument("--all", action="store_true", help="装到所有支持的 agent")
    p.add_argument("--yes", action="store_true", help="全部用默认值，不提问")
    p.add_argument("--deps", action="store_true", help="自动安装可选依赖")
    p.add_argument("--uninstall", action="store_true", help="卸载")
    args = p.parse_args()

    if args.uninstall:
        do_uninstall()
        return 0

    say("=" * 52)
    say(" deepseek-eyes 安装器 —— 给纯文本模型装上眼睛")
    say("=" * 52)
    say("原理：你的 agent 平时照旧用 DeepSeek，只有遇到图片时")
    say("      才把这张图单独发给配置好的某个多模态后端转成文字，按张付费。")
    say("      可以接 Luna、GPT-4o、Qwen-VL，或任意 OpenAI 兼容中转站。")
    say()

    step_copy_script()
    cfg = step_config(args)
    step_install_targets(args)
    step_deps(args)
    step_check(cfg)

    say()
    say("=" * 52)
    say("装完了。重启一下 agent 软件让它读到新技能，然后直接说：")
    say('  「看看这张图 D:\\shots\\a.png」')
    say("它就会用默认后端（%s）自己调用眼睛。" % cfg.get("default_backend", "?"))
    say("要用别的模型就加 --backend，例如：")
    say('  %s a.png --backend gpt4o' % see_cmd())
    say("=" * 52)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(130)
