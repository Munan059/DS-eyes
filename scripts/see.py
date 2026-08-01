#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deepseek-eyes / see.py  (轻量版)

给纯文本大模型外接一副眼睛。

宿主 agent（跑在 DeepSeek 等纯文本模型上）遇到图片时调用本脚本，
脚本把图片交给某个支持图片输入的多模态模型，把"看到的东西"转成详细文字返回。

后端统一走 OpenAI 兼容协议（GPT-5.6 Luna、GPT-4o、Qwen-VL，或任意 OpenAI 兼容中转站）。
想用 Gemini：把 base_url 填成它的 OpenAI 兼容地址即可；想用 Claude：走一个 OpenAI 兼容中转站。

支持多个后端、多把 key：在 ~/.deepseek-eyes/config.json 里写一组命名后端，
调用时用 --backend <名字> 选，不指定就用 default_backend。图片一律 base64 编码。

只依赖 Python 标准库即可运行。可选依赖：Pillow（图片压缩省钱）。

用法示例：
  python see.py shot.png                         # 用默认后端看
  python see.py shot.png --backend gpt4o        # 指定用 gpt4o 后端
  python see.py shot.png -q "右下角那个红色数字是多少"
  python see.py a.png b.png -q "对比这两张图的区别"
  python see.py --check
  python see.py --list-backends
"""

import argparse
import base64
import io
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

__version__ = "3.0.0"

# ---------------------------------------------------------------- 基础设置

HOME_DIR = os.path.join(os.path.expanduser("~"), ".deepseek-eyes")
CONFIG_PATH = os.path.join(HOME_DIR, "config.json")

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.6-luna"

# GPT-5.6 Luna 2026-07-30 降价后的官方价格（美元 / 百万 token），仅作默认参考。
# 其它后端请在配置文件里各自填写，没填则不显示费用（避免瞎猜）。
PRICE_IN = 0.20
PRICE_CACHED_IN = 0.02
PRICE_OUT = 1.20
USD_TO_CNY = 7.2

UA = "deepseek-eyes/%s" % __version__

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
MAX_IMAGE_BYTES = 18 * 1024 * 1024  # 单张图 base64 前的上限

if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台中文不乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------- 提示词

COMMON_RULE = (
    "你是一双给纯文本大模型服务的眼睛。对方看不见任何图像，只能读你写的文字，"
    "然后据此做判断和写代码。所以你的描述必须精确、具体、可核对。\n"
    "铁律：\n"
    "1. 只描述图里真实存在的东西，看不清就写「看不清」，绝对不要猜测或补全。\n"
    "2. 图中出现的文字一律原样照抄（含大小写、标点、数字、单位），不要翻译、不要润色。\n"
    "3. 涉及数值、坐标、报错行号时逐个列出，不要用「若干」「一些」这类模糊词。\n"
    "4. 用中文书写说明性内容，图内原文保留原语言。\n"
)

DESCRIBE_PROMPT = (
    "请详细描述这张图。按下面顺序写：\n"
    "一、一句话总述：这是什么东西的什么画面。\n"
    "二、整体结构：画面分成哪几块，各在什么位置。\n"
    "三、逐块细节：每一块里有什么元素、什么文字、什么数字、什么颜色。\n"
    "四、图中全部可见文字：逐条原样列出。\n"
    "五、值得注意的地方：异常、错误、突出项、和常规不同之处。"
)


# ---------------------------------------------------------------- 配置读取


def load_config():
    """配置优先级：命令行 > 环境变量 > ~/.deepseek-eyes/config.json > 默认值。

    支持两种写法：
      - 新版（推荐）：{"default_backend": "luna", "backends": {"luna": {...}, "gpt4o": {...}}}
      - 旧版（兼容）：顶层直接写 api_key/base_url/model，会被当成名为 luna 的后端。
    所有后端都走 OpenAI 兼容协议，配置里旧版的 provider 字段会被忽略。
    """
    cfg = {
        "usd_to_cny": USD_TO_CNY,
        "max_side": 1536,
        "default_backend": "",
        "backends": {},
        "_source": "默认值",
        "_old_format": False,
    }

    file_cfg = {}
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            if not isinstance(file_cfg, dict):
                file_cfg = {}
        except Exception as e:
            warn("配置文件读取失败（%s）：%s" % (CONFIG_PATH, e))
            file_cfg = {}

    cfg["usd_to_cny"] = file_cfg.get("usd_to_cny", USD_TO_CNY)
    cfg["max_side"] = file_cfg.get("max_side", 1536)

    # 旧版兼容：顶层直接写 api_key / base_url / model
    if "backends" not in file_cfg:
        if file_cfg.get("api_key") or file_cfg.get("base_url") or file_cfg.get("model") or file_cfg.get("price_in"):
            cfg["backends"]["luna"] = _norm_backend({
                "api_key": file_cfg.get("api_key", ""),
                "base_url": file_cfg.get("base_url", "") or DEFAULT_BASE_URL,
                "model": file_cfg.get("model", "") or DEFAULT_MODEL,
                "price_in": file_cfg.get("price_in", PRICE_IN),
                "price_cached_in": file_cfg.get("price_cached_in", PRICE_CACHED_IN),
                "price_out": file_cfg.get("price_out", PRICE_OUT),
            })
            cfg["default_backend"] = "luna"
            cfg["_old_format"] = True
            cfg["_source"] = CONFIG_PATH
        return cfg

    # 新版：backends 字典
    backends = {}
    for name, b in (file_cfg.get("backends") or {}).items():
        if not isinstance(b, dict):
            continue
        backends[name] = _norm_backend(b)
    cfg["backends"] = backends
    cfg["default_backend"] = file_cfg.get("default_backend") or (next(iter(backends)) if backends else "")
    cfg["_source"] = CONFIG_PATH
    return cfg


def _norm_backend(b):
    """补默认值，并去掉轻量版不支持的 provider 字段。"""
    b = dict(b)
    b.setdefault("api_key", "")
    b.setdefault("base_url", DEFAULT_BASE_URL)
    b.setdefault("model", DEFAULT_MODEL)
    b.pop("provider", None)
    return b


def resolve_backend(cfg, args):
    """根据 --backend / 环境变量 / default_backend 选出要用的后端，并应用命令行覆盖。"""
    if not cfg["backends"]:
        return None, None
    name = (
        args.backend
        or os.environ.get("DEESEEK_EYES_BACKEND")
        or cfg.get("default_backend")
        or next(iter(cfg["backends"]))
    )
    if name not in cfg["backends"]:
        die(
            "找不到名为「%s」的后端。配置里现有的后端：%s\n"
            "用 --backend <名字> 指定其中一个。" % (name, "、".join(cfg["backends"].keys()))
        )
    backend = dict(cfg["backends"][name])
    backend["_name"] = name

    if args.api_key:
        backend["api_key"] = args.api_key
    if args.base_url:
        backend["base_url"] = args.base_url.rstrip("/")
    if args.model:
        backend["model"] = args.model

    # OpenAI 系兼容老的 LUNA/OPENAI 环境变量 key
    if not backend.get("api_key"):
        env_key = os.environ.get("LUNA_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if env_key:
            backend["api_key"] = env_key
    return name, backend


def warn(msg):
    sys.stderr.write("[deepseek-eyes] %s\n" % msg)


def die(msg, code=1):
    sys.stderr.write("[deepseek-eyes] 出错：%s\n" % msg)
    sys.exit(code)


# ---------------------------------------------------------------- 图片处理


def is_url(s):
    return s.startswith("http://") or s.startswith("https://")


def fetch_url_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def shrink_image(raw, max_side):
    """有 Pillow 就把长边压到 max_side 以内，省钱又省时间；没有就原样返回。"""
    if max_side <= 0:
        return raw, None
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return raw, None

    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
        w, h = im.size
        if max(w, h) <= max_side and len(raw) < 2 * 1024 * 1024:
            return raw, "%dx%d" % (w, h)
        scale = min(1.0, float(max_side) / max(w, h))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        if scale < 1.0:
            im = im.resize((nw, nh), Image.LANCZOS)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85, optimize=True)
        out = buf.getvalue()
        if len(out) >= len(raw) and max(w, h) <= max_side:
            return raw, "%dx%d" % (w, h)
        return out, "%dx%d->%dx%d" % (w, h, nw, nh)
    except Exception as e:
        warn("图片压缩失败，改用原图：%s" % e)
        return raw, None


def sniff_mime(raw, fallback):
    """按文件头判断真实类型，避免扩展名骗人。"""
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return fallback


def collect_images(inputs, max_side):
    """把输入的路径/网址统统变成 [(bytes, mime, 标签)]。"""
    items = []
    for src in inputs:
        if is_url(src):
            try:
                raw = fetch_url_bytes(src)
            except Exception as e:
                die("图片下载失败 %s：%s" % (src, e))
            mime = mimetypes.guess_type(src)[0] or "image/png"
            raw, _ = shrink_image(raw, max_side)
            items.append((raw, sniff_mime(raw, mime), os.path.basename(urllib.parse.urlparse(src).path) or src))
            continue

        path = os.path.abspath(os.path.expanduser(src))
        if not os.path.isfile(path):
            die("找不到文件：%s" % path)
        ext = os.path.splitext(path)[1].lower()
        if ext and ext not in IMAGE_EXTS:
            warn("%s 看起来不是图片格式，仍然尝试按图片发送" % os.path.basename(path))

        with open(path, "rb") as f:
            raw = f.read()
        raw, _ = shrink_image(raw, max_side)
        mime = mimetypes.guess_type(path)[0] or "image/png"
        items.append((raw, sniff_mime(raw, mime), os.path.basename(path)))

    if not items:
        die("没有可看的图片")
    for raw, _, label in items:
        if len(raw) > MAX_IMAGE_BYTES:
            die(
                "%s 压缩后仍有 %.1f MB，太大了。装个 Pillow 可自动压缩：\n"
                '  "%s" -m pip install pillow' % (label, len(raw) / 1024.0 / 1024, sys.executable)
            )
    return items


# ---------------------------------------------------------------- 请求构造（OpenAI 兼容）

CLAUDE_IMAGE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")


def build_instruction(question):
    instruction = DESCRIBE_PROMPT
    if question:
        instruction += "\n\n另外请特别回答：" + question
    return instruction


def _image_blocks(items):
    """把图片列表变成 [(b64, mime, label)]，多图时附带图号标签。"""
    multi = len(items) > 1
    out = []
    for i, (raw, mime, label) in enumerate(items, 1):
        b64 = base64.b64encode(raw).decode("ascii")
        tag = ("【图%d：%s】" % (i, label)) if multi else None
        out.append((b64, mime, tag))
    return out


def build_request(backend, items, instruction, max_tokens):
    """OpenAI 兼容协议：Luna / GPT-4o / Qwen-VL / 各种中转站。图片用 base64 data URL。"""
    content = [{"type": "text", "text": instruction}]
    for b64, mime, tag in _image_blocks(items):
        if tag:
            content.append({"type": "text", "text": tag})
        content.append(
            {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, b64)}}
        )
    body = {
        "model": backend["model"],
        "messages": [
            {"role": "system", "content": COMMON_RULE},
            {"role": "user", "content": content},
        ],
        "max_completion_tokens": max_tokens,
    }
    url = backend["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % backend["api_key"],
        "User-Agent": UA,
    }
    return url, headers, body


# ---------------------------------------------------------------- 响应解析


def openai_extract(resp):
    try:
        choice = resp["choices"][0]
    except (KeyError, IndexError, TypeError):
        return "", {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
    msg = choice.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):  # 少数网关返回分块结构
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("text"):
                parts.append(c["text"])
            elif isinstance(c, str):
                parts.append(c)
        text = "\n".join(parts).strip()
    else:
        text = (content or "").strip()
    usage = resp.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    return text, {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "cached_tokens": details.get("cached_tokens", 0) or 0,
    }


# ---------------------------------------------------------------- 网络与调用


def post_json(url, body, headers, timeout):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_model(name, backend, items, instruction, max_tokens, timeout, retries=2):
    """构造请求并调用，自动兼容新旧参数名、重试与友好报错。"""
    url, headers, body = build_request(backend, items, instruction, max_tokens)
    last_err = None

    for attempt in range(retries + 1):
        try:
            resp = post_json(url, body, headers, timeout)
            text, usage = openai_extract(resp)
            return resp, text, usage
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            low = detail.lower()

            # 老接口 / 部分中转站只认 max_tokens，不认 max_completion_tokens
            if e.code == 400 and "max_completion_tokens" in low and "max_completion_tokens" in body:
                body["max_tokens"] = body.pop("max_completion_tokens")
                continue

            if e.code in (401, 403):
                die("接口拒绝了这个 key（HTTP %d）。请检查 %s 里 %s 后端的 api_key 和 base_url 是否配套。\n服务端原话：%s"
                    % (e.code, CONFIG_PATH, name, detail[:500]))
            if e.code == 404:
                die("找不到模型或地址（HTTP 404）。当前 %s 后端的 base_url=%s，model=%s。\n中转站地址通常要带 /v1 结尾，模型名也可能不一样。\n服务端原话：%s"
                    % (name, backend["base_url"], backend["model"], detail[:500]))
            if e.code == 429 or e.code >= 500:
                last_err = "HTTP %d %s" % (e.code, detail[:300])
                if attempt < retries:
                    time.sleep(2 ** attempt * 2)
                    continue
            die("请求失败 HTTP %d：%s" % (e.code, detail[:800]))
        except urllib.error.URLError as e:
            last_err = str(e.reason)
            if attempt < retries:
                time.sleep(2 ** attempt * 2)
                continue
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(2 ** attempt * 2)
                continue

    die(
        "连不上接口（%s）。%s\n最后一次错误：%s"
        % (backend.get("base_url", "接口"), _conn_hint(), last_err)
    )


def _conn_hint():
    return "国内直连 api.openai.com 通常不通，可以换成中转站地址，或给终端设置代理环境变量 HTTPS_PROXY"


def cost_line(usage, backend, usd_to_cny, elapsed):
    pin = usage.get("prompt_tokens", 0)
    pout = usage.get("completion_tokens", 0)
    cachedn = usage.get("cached_tokens", 0) or 0

    price_in = backend.get("price_in")
    price_out = backend.get("price_out")
    price_cached_in = backend.get("price_cached_in", 0)
    if price_in is None or price_out is None:
        tag = "（该后端未配置价格，不显示费用）"
    else:
        fresh = max(0, pin - cachedn)
        usd = (fresh * price_in + cachedn * price_cached_in + pout * price_out) / 1_000_000.0
        cny = usd * float(usd_to_cny or USD_TO_CNY)
        tag = "约 ¥%.4f" % cny
    return "> 眼睛[%s/%s]：用时 %.1fs · 输入 %d tok（缓存 %d）· 输出 %d tok · %s" % (
        backend.get("_name", "?"),
        backend.get("model", "?"),
        elapsed,
        pin,
        cachedn,
        pout,
        tag,
    )


# ---------------------------------------------------------------- 自检 / 后端列表


def list_backends(cfg):
    print("已配置的后端（%d 个）：" % len(cfg["backends"]))
    for name, b in cfg["backends"].items():
        mark = " ← 默认" if name == cfg["default_backend"] else ""
        key = b.get("api_key", "")
        masked = (key[:6] + "..." + key[-4:]) if len(key) > 12 else ("(空)" if not key else "***")
        print("  · %s  model=%s  key=%s  base=%s%s" % (
            name, b.get("model", "?"), masked, b.get("base_url", ""), mark,
        ))
    print("默认后端：%s" % (cfg["default_backend"] or "(无)"))


def do_check(cfg, args):
    print("deepseek-eyes v%s 自检" % __version__)
    print("-" * 48)
    print("配置来源  : %s" % cfg["_source"])
    print("配置文件  : %s%s" % (CONFIG_PATH, "" if os.path.isfile(CONFIG_PATH) else "（不存在）"))
    if cfg.get("_old_format"):
        print("           （检测到旧版单配置，已按 luna 后端兼容读取）")
    print("-" * 48)
    if not cfg["backends"]:
        print("还没配置任何后端。运行 install.py，或手工编辑配置文件加上 backends。")
        return 2

    list_backends(cfg)
    print("-" * 48)

    name, backend = resolve_backend(cfg, args)
    if not backend:
        return 2
    key = backend.get("api_key", "")
    if not key:
        print("结论：后端「%s」还没填 API key。先跑一次 install.py，或手工编辑配置文件。" % name)
        return 2

    print("正在用后端「%s」发一个最小请求测试连通……" % name)
    t0 = time.time()
    try:
        _, text, _ = call_model(name, backend, [], "回复两个字：可用", 200, args.timeout, retries=1)
    except SystemExit:
        return 1
    except Exception as e:
        print("失败：%s" % e)
        return 1
    print("成功：模型回了「%s」，耗时 %.1fs" % (text[:40] or "(空)", time.time() - t0))
    print("眼睛可以用了。")
    return 0


# ---------------------------------------------------------------- 主流程


def build_parser():
    p = argparse.ArgumentParser(
        prog="see.py",
        description="给纯文本模型外接一副眼睛：把图片交给多模态模型看，返回详细文字。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="所有后端都走 OpenAI 兼容协议；图片一律 base64 编码。",
    )
    p.add_argument("inputs", nargs="*", help="图片路径或图片网址，可以给多个")
    p.add_argument("-q", "--question", default="", help="要额外回答的具体问题")
    p.add_argument("--backend", default="", help="用哪个后端（config.json 里 backends 的名字），默认 default_backend")
    p.add_argument("--json", action="store_true", help="输出 JSON，方便程序解析")
    p.add_argument("--max-side", type=int, default=None, help="图片长边压到多少像素，0 表示不压，默认 1536")
    p.add_argument("--max-tokens", type=int, default=8000, help="回答长度上限，默认 8000")
    p.add_argument("--timeout", type=int, default=180, help="单次请求超时秒数，默认 180")
    p.add_argument("--api-key", default="", help="临时覆盖当前后端的 key")
    p.add_argument("--base-url", default="", help="临时覆盖当前后端的接口地址")
    p.add_argument("--model", default="", help="临时覆盖当前后端的模型名")
    p.add_argument("--dry-run", action="store_true", help="只打印将要发送的请求摘要，不真的调用")
    p.add_argument("--list-backends", action="store_true", help="列出已配置的后端并退出")
    p.add_argument("--check", action="store_true", help="自检：看配置、依赖和连通性")
    p.add_argument("-v", "--version", action="version", version="deepseek-eyes %s" % __version__)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    cfg = load_config()

    if args.list_backends:
        if not cfg["backends"]:
            print("还没配置任何后端。运行 install.py 进行配置。")
            return 0
        list_backends(cfg)
        return 0

    if args.check:
        return do_check(cfg, args)

    if not args.inputs:
        build_parser().print_help()
        return 0

    name, backend = resolve_backend(cfg, args)
    if not backend:
        die(
            "配置文件 %s 里没有任何后端。请运行 install.py，或手工加上 backends 配置。\n"
            "参考：{\"default_backend\": \"luna\", \"backends\": {\"luna\": {\"api_key\": \"...\", "
            "\"model\": \"gpt-5.6-luna\"}}}" % CONFIG_PATH
        )

    if not backend.get("api_key") and not args.dry_run:
        die(
            "后端「%s」还没配置 API key。三选一：\n"
            "  1) 跑一次安装脚本 install.py，按提示填；\n"
            "  2) 编辑 %s，在 backends.%s 里写入 api_key；\n"
            "  3) 用环境变量 LUNA_API_KEY / OPENAI_API_KEY。"
            % (name, CONFIG_PATH, name)
        )

    max_side = cfg.get("max_side", 1536) if args.max_side is None else args.max_side

    t0 = time.time()
    items = collect_images(args.inputs, max_side)
    instruction = build_instruction(args.question)

    if args.dry_run:
        url, headers, body = build_request(backend, items, instruction, args.max_tokens)
        total = sum(len(raw) for raw, _, _ in items)
        print("将要发送：")
        print("  后端   : %s" % name)
        print("  接口   : %s" % url.split("?")[0])
        print("  模型   : %s" % backend["model"])
        print("  图片   : %d 张，压缩后合计 %.1f KB" % (len(items), total / 1024.0))
        for i, (raw, mime, label) in enumerate(items, 1):
            print("    %d. %s  %s  %.1f KB" % (i, label, mime, len(raw) / 1024.0))
        print("  指令   : %s" % instruction[:200].replace("\n", " / "))
        print("  预计输入 token ≈ %d（图片按面积估算）" % int(total / 750 + 400))
        return 0

    resp, text, usage = call_model(name, backend, items, instruction, args.max_tokens, args.timeout)
    elapsed = time.time() - t0

    if not text:
        finish = (resp.get("choices") or [{}])[0].get("finish_reason")
        die(
            "模型没返回内容（finish_reason=%s）。若是 length，说明预算被吃光了，"
            "可以加大 --max-tokens。" % finish
        )

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "backend": name,
                    "model": backend["model"],
                    "images": [lbl for _, _, lbl in items],
                    "text": text,
                    "usage": usage,
                    "elapsed_sec": round(elapsed, 2),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(text)
        print()
        print(cost_line(usage, backend, cfg.get("usd_to_cny", USD_TO_CNY), elapsed))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
