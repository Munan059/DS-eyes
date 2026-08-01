<div align="center">

[English](README_EN.md) | 中文

# deepseek-eyes

**给 DeepSeek 这类纯文本模型外接一副眼睛：只在撞见图片的那一秒，把那一张图单独发给多模态模型转成文字——平时零额外开销、零额外依赖，也不改动你原有的模型与配置。**

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB)
![依赖](https://img.shields.io/badge/依赖-仅标准库-2ea44f)
![支持](https://img.shields.io/badge/支持-5%2B%20种%20agent-1f6feb)
![License](https://img.shields.io/badge/License-MIT-green)

[这是什么](#-这是什么) · [快速开始](#-快速开始) · [功能亮点](#-功能亮点) · [架构设计](#-架构设计) · [目录结构](#-目录结构) · [怎么用](#-怎么用) · [接多个模型](#-接多个模型) · [成本](#-成本) · [常见问题](#-常见问题) · [致谢](#-致谢)

</div>

---

## 📖 这是什么

DeepSeek V4 的接口只认文字，看不见图。这个工具不换模型、不改配置，只是在你的 agent 撞见图片时，把那一张图单独发给一个支持视觉的多模态模型，拿回一段足够详细的文字，再交还给 DeepSeek 继续干活。

不止能接一个模型：你可以同时配置好几个多模态后端（各用各的 key），平时用默认那个，想换模型时一句话指定。图片一律 base64 编码后发送，所有后端都走 OpenAI 兼容协议。

> **为什么值得一看**：它不是"整段对话切换到多模态模型"，而是按张外包。纯文字任务仍然走你原来的 DeepSeek，只有真正需要眼睛时才会调用多模态后端，平时一点额外开销都没有。

## 🚀 快速开始

### 环境要求

- Python 3.8 以上
- 至少一个支持图片输入的多模态识别模型 API key（OpenAI 官方，或任意 OpenAI 兼容中转站）

> DeepSeek 的 key 不用在这里填——那是你 agent 软件自己在用的。

### 1️⃣ 运行安装器

```bash
python install.py
```

Windows 上如果提示找不到 python，把前面换成 Python 的完整路径，例如：

```bash
"C:\Users\你的用户名\AppData\Local\Programs\Python\Python312\python.exe" install.py
```

### 2️⃣ 按提示添加后端（可加多个）

每加一个后端，回答这几项；想接几个就加几个，最后选一个做默认：

| 问题 | 怎么答 |
| --- | --- |
| 后端名字 | 给这组 key 起个名，比如 `luna` / `gpt4o` / `qwen` |
| 接口地址 | 选 1 OpenAI 官方 · 2 中转站（如 openrouter），或自己粘贴地址 |
| API key | 粘贴对应后端的 key |
| 模型名 | 一般直接回车用默认；用中转站时可能要改成它家的模型名 |
| 还要加吗 | 回车结束，或输 y 继续加下一个 |

安装器会自动跑一次自检，看到"眼睛可以用了"就成了。

### 3️⃣ 重启 agent 软件，直接说人话

```
看看这张图 D:\shots\bug.png
```

它自己就会调用眼睛，不需要你记任何命令。

<details>
<summary>不想交互？一条命令装完</summary>

```bash
python install.py --backend luna --api-key sk-你的key --base-url https://api.openai.com/v1 --all --yes
```

加第二个后端（比如 GPT-4o）再跑一次，用 `--backend` 区分：

```bash
python install.py --backend gpt4o --api-key sk-你的key --base-url https://api.openai.com/v1 --yes
```

可用参数：`--targets workbuddy,claude` 只装指定软件、`--deps` 顺带装可选依赖、`--uninstall` 卸载。

</details>

## ✨ 功能亮点

- **🔌 零依赖** — 核心脚本只用 Python 标准库，装完就能跑。Pillow 是可选的，只用来压缩大图省钱
- **🎯 一个模式讲清楚** — 默认做通用详细描述；写上 `-q` 就只回答那个具体问题，比笼统的"描述一下"更省 token
- **🧩 一次装遍所有 agent** — WorkBuddy、Claude Code、Codex、Trae、ZCode，以及任何认 `AGENTS.md` 的工具
- **🚀 多模型随便切** — 同时接 Luna、GPT-4o、Qwen-VL，用 `--backend 名字` 切换，各带各的 key
- **💰 每次报账** — 调用结束打印真实 token 数和费用；没配价格就不瞎猜

## 🏗 架构设计

任务进来后，工具只在一张图出现时才唤醒多模态后端，其余时间 DeepSeek 照常工作：

```
任务来了
   │
   ├── 没有图 ──────────────────► DeepSeek 照常干活，不产生任何额外调用
   │
   └── 有图 ──► 某个多模态后端看图 ──► 转成详细文字 ──► DeepSeek 拿着文字继续干活
```

几个关键决策：

- **按张外包，而不是整段切换**：只有"有图"的那一瞬间才发起一次多模态调用，文字任务零开销。
- **纯标准库**：`see.py` 不依赖任何第三方包，下载即用，不会因为环境缺库而跑不起来。
- **统一走 OpenAI 兼容协议**：Luna、GPT-4o、Qwen-VL 甚至 Gemini、Claude（经中转）都接同一套接口，新增后端只改配置。
- **图片一律 base64 内联**：不需要额外的图床或文件服务，一张图就是一个请求。

## 📂 目录结构

```
deepseek-eyes/
├── install.py          # 一键安装器，你只跟它打交道
├── SKILL.md            # 给 agent 读的说明书，安装时分发到各软件
└── scripts/
    └── see.py          # 真正干活的"眼睛"，纯标准库
```

装完之后长这样：

```
~/.deepseek-eyes/
├── config.json         # 后端和 key  ⬅ 唯一存着你隐私的文件
├── see.py
└── SKILL.md
```

Windows 上 `~` 就是 `C:\Users\你的用户名`。

## 🔧 怎么用

日常你不用敲命令，agent 会自己调。下面是它背后实际执行的东西，你也可以手动跑：

```bash
python ~/.deepseek-eyes/see.py <图片路径> [-q "具体问题"] [--backend 后端名]
```

不写 `-q` 时做通用详细描述；写了 `-q` 就只回答那个具体问题。可以给多张图，多图时脚本会标好图号。

### 几个例子

```bash
python ~/.deepseek-eyes/see.py bug.png
python ~/.deepseek-eyes/see.py design.png -q "这个界面用了哪些主色，给十六进制色值"
python ~/.deepseek-eyes/see.py before.png after.png -q "对比这两张图的区别"
python ~/.deepseek-eyes/see.py dashboard.png --backend gpt4o        # 改用 gpt4o 看
```

其他参数：`--json` 结构化输出、`--max-side 2048` 图太糊时提高清晰度、`--check` 自检、`--list-backends` 看已配置的后端。

## 🔌 接多个模型

配置文件 `~/.deepseek-eyes/config.json` 里写一组命名后端，每个后端各带自己的 key。不写 `--backend` 时用 `default_backend`，要换模型就加 `--backend 名字`。

```json
{
  "default_backend": "luna",
  "backends": {
    "luna":  {"api_key": "sk-...", "base_url": "https://api.openai.com/v1", "model": "gpt-5.6-luna"},
    "gpt4o": {"api_key": "sk-...", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
    "qwen":  {"api_key": "sk-...", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-vl-max"}
  }
}
```

所有后端都走 OpenAI 兼容协议（图片统一 base64）：

- **想用 Gemini** — 把 `base_url` 填成它的 OpenAI 兼容地址（形如 `https://generativelanguage.googleapis.com/v1beta/openai`），模型写 `gemini-2.0-flash`
- **想用 Claude** — 走一个 OpenAI 兼容中转站，把 key 和地址填进对应后端即可

> **默认后端**：把最常用的那个写成 `default_backend` 就行。其它模型随用随切，互不影响 key。

## 💰 成本

多模态模型按量计费，单价看你用的后端（写在配置文件里）。下面以默认后端 Luna 的官方定价为例（人民币按汇率 7.2 折算）：

| 计费项 | 每百万 token | 折合人民币 |
| --- | --- | --- |
| 输入 | $0.20 | ¥1.44 |
| 输入（缓存命中） | $0.02 | ¥0.14 |
| 输出 | $1.20 | ¥8.64 |

> 上表是 Luna 的官方公开单价，不是本项目的实测数据。单张截图的实际花费尚未跑通真实调用，等测过再补进来；其它后端有各自的价格，请在配置文件对应后端里填 `price_in` / `price_out`，没填时脚本会显示"未配置价格"而不瞎猜。

不用自己算，每次调用结束脚本都会打印这一行真实用量（数字为格式示意）：

```
> 眼睛[luna/gpt-5.6-luna] · 用时 3.2s · 输入 1234 tok（缓存 0）· 输出 567 tok · 约 ¥0.0000
```

一条省钱习惯：想问的一次写进 `-q` 问全；纯文字任务不要调这个脚本。

## ❓ 常见问题

先跑一次自检，它会列出所有后端（含模型 / key 掩码），并试连默认后端一次：

```bash
python ~/.deepseek-eyes/see.py --check
python ~/.deepseek-eyes/see.py --list-backends    # 只看后端列表
```

| 现象 | 原因和处理 |
| --- | --- |
| 提示没有任何后端 | 重跑 `install.py` 在配置里加上 `backends` |
| 提示某后端没配 api_key | 编辑 `~/.deepseek-eyes/config.json`，在该后端里填 `api_key` |
| HTTP 401 / 403 | key 和后端不配套（官方 key 配了中转地址，或反过来） |
| HTTP 404 | 模型名写错；中转站地址要带 `/v1` 结尾 |
| 连不上、超时 | 国内直连 `api.openai.com` 通常不通，换中转站或设 `HTTPS_PROXY` |
| agent 装了却不调用 | 重启软件让它重新读技能；或在对话里明说"用 deepseek-eyes 看这张图" |

<details>
<summary>手工改配置</summary>

`~/.deepseek-eyes/config.json`：

```json
{
  "default_backend": "luna",
  "backends": {
    "luna":  {"api_key": "sk-xxx", "base_url": "https://api.openai.com/v1", "model": "gpt-5.6-luna"},
    "gpt4o": {"api_key": "sk-xxx", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"}
  }
}
```

也支持环境变量 `DEESEEK_EYES_BACKEND` 选后端；OpenAI 系还可用 `LUNA_API_KEY` / `OPENAI_API_KEY`，优先级高于配置文件。

</details>

## 🙏 致谢

- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) — 这副眼睛的视网膜（OpenAI 兼容后端默认用它）
- [DeepSeek API](https://api-docs.deepseek.com/) — 负责思考的大脑
- [Pillow](https://github.com/python-pillow/Pillow) — 可选的图片压缩

## 📄 License

MIT

<div align="center">

觉得有用点个 ⭐

</div>
