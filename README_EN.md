<div align="center">

[中文](README.md) | **English**

# deepseek-eyes

**Give DeepSeek-class text-only models a pair of eyes: the moment an image shows up, outsource just that one picture to a multimodal model and get text back — zero extra cost or dependency the rest of the time, and your existing model and config stay untouched.**

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB)
![Dependencies](https://img.shields.io/badge/dependencies-stdlib%20only-2ea44f)
![Agents](https://img.shields.io/badge/supports-5%2B%20agents-1f6feb)
![License](https://img.shields.io/badge/License-MIT-green)

[What is this](#-what-is-this) · [Quick start](#-quick-start) · [Features](#-features) · [Architecture](#-architecture) · [Project layout](#-project-layout) · [Usage](#-usage) · [Multiple models](#-multiple-models) · [Cost](#-cost) · [Troubleshooting](#-troubleshooting) · [Acknowledgements](#-acknowledgements)

</div>

---

## 📖 What is this

The DeepSeek V4 API only accepts text — it cannot see images. This tool doesn't switch your model
or change your setup. It simply takes that one image your agent ran into, sends it to a multimodal
model that does accept image input, gets back a detailed text description, and hands it to DeepSeek
to carry on.

It is not limited to one model: you can configure several multimodal backends at once (each with its
own key), use the default one day to day, and pick a different model with a single flag when you want.
Images are always sent base64-encoded, and every backend speaks the OpenAI-compatible protocol.

> **Why it's worth a look**: this is not "switch the whole conversation to a multimodal model".
> It's per-image outsourcing. Text-only tasks still run on your existing DeepSeek, and a multimodal
> backend is called only when eyes are genuinely needed — at zero cost the rest of the time.

## 🚀 Quick start

### Requirements

- Python 3.8 or newer
- At least one API key for an image-capable multimodal model (OpenAI, or any OpenAI-compatible relay)

> Your DeepSeek key does not go here — that one belongs to your agent app.

### 1️⃣ Run the installer

```bash
python install.py
```

On Windows, if `python` isn't found, use the full path instead:

```bash
"C:\Users\YourName\AppData\Local\Programs\Python\Python312\python.exe" install.py
```

### 2️⃣ Add backends (as many as you like)

For each backend, answer a few prompts; add as many as you want, then pick one to be the default:

| Question | What to answer |
| --- | --- |
| Backend name | Name this key set, e.g. `luna` / `gpt4o` / `qwen` |
| Base URL | 1 OpenAI official · 2 a relay (e.g. openrouter), or paste your own address |
| API key | Paste the key for that backend |
| Model name | Usually just press Enter for the default; relays may need their own model name |
| Add another? | Press Enter to finish, or `y` to add the next one |

The installer runs a self-check at the end. When you see "眼睛可以用了" (the eyes are ready), you're done.

### 3️⃣ Restart your agent app and just talk

```
Take a look at this image D:\shots\bug.png
```

It calls the eyes on its own. You don't need to memorize any command.

<details>
<summary>Prefer non-interactive? One command</summary>

```bash
python install.py --backend luna --api-key sk-your-key --base-url https://api.openai.com/v1 --all --yes
```

Add a second backend (e.g. GPT-4o) with another run, using `--backend` to tell them apart:

```bash
python install.py --backend gpt4o --api-key sk-your-key --base-url https://api.openai.com/v1 --yes
```

Other flags: `--targets workbuddy,claude` to install for specific apps, `--deps` to also install
optional dependencies, `--uninstall` to remove.

</details>

## ✨ Features

- **🔌 Zero dependencies** — the core script uses only the Python standard library. Pillow is optional, for shrinking big images
- **🎯 One mode that says it clearly** — a general detailed description by default; add `-q` to ask only that one question, cheaper than a vague "describe this"
- **🧩 Install once, works everywhere** — WorkBuddy, Claude Code, Codex, Trae, ZCode, and anything that reads `AGENTS.md`
- **🚀 Switch models freely** — wire up Luna / GPT-4o / Qwen-VL together, switch with `--backend name`, each with its own key
- **💰 Receipt every time** — prints real token counts and cost after each call; if no price is configured it simply won't guess

## 🏗 Architecture

After a task arrives, the tool only wakes a multimodal backend when an image actually shows up;
otherwise DeepSeek carries on as usual:

```
A task arrives
   │
   ├── No image ────────────────► DeepSeek works as usual, no extra call at all
   │
   └── Image ──► a multimodal backend looks ──► turns it into text ──► DeepSeek continues with that text
```

A few key decisions:

- **Per-image, not whole-conversation**: a multimodal call fires only at the instant an image appears; text tasks cost nothing.
- **Pure standard library**: `see.py` depends on no third-party package, so it runs the moment you download it — no "missing library" surprises.
- **One OpenAI-compatible protocol for everything**: Luna, GPT-4o, Qwen-VL, and even Gemini or Claude (via a relay) all plug into the same interface; adding a backend is a config edit.
- **Images are always base64-inlined**: no extra image host or file service needed — one image is one request.

## 📂 Project layout

```
deepseek-eyes/
├── install.py          # the installer — the only file you interact with
├── SKILL.md            # the manual your agent reads, distributed on install
└── scripts/
    └── see.py          # the actual "eyes", pure standard library
```

After installation:

```
~/.deepseek-eyes/
├── config.json         # backends and keys  ⬅ the only file holding your secret
├── see.py
└── SKILL.md
```

On Windows `~` means `C:\Users\YourName`.

## 🔧 Usage

Day to day you don't type commands — your agent does it. Here's what runs under the hood, which you
can also invoke yourself:

```bash
python ~/.deepseek-eyes/see.py <image path> [-q "your question"] [--backend name]
```

Without `-q` you get a general detailed description; with `-q` it answers only that question.
You can pass several images; when you do, the script labels each one by number.

### Examples

```bash
python ~/.deepseek-eyes/see.py bug.png
python ~/.deepseek-eyes/see.py design.png -q "What are the main colours, give hex values"
python ~/.deepseek-eyes/see.py before.png after.png -q "What's the difference between these two images"
python ~/.deepseek-eyes/see.py dashboard.png --backend gpt4o        # use gpt4o instead
```

Other flags: `--json` for structured output, `--max-side 2048` when the image is too blurry,
`--check` for a self-test, `--list-backends` to list configured backends.

## 🔌 Multiple models

In `~/.deepseek-eyes/config.json` write a set of named backends, each with its own key.
Without `--backend` the `default_backend` is used; add `--backend name` to switch models.

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

Every backend speaks the OpenAI-compatible protocol (images are always base64):

- **Want Gemini** — set `base_url` to its OpenAI-compatible endpoint (like `https://generativelanguage.googleapis.com/v1beta/openai`), model `gemini-2.0-flash`
- **Want Claude** — use an OpenAI-compatible relay; put its key and URL in the matching backend

> **Default backend**: set the one you use most often as `default_backend`. Other models are switched
> on demand and never share keys.

## 💰 Cost

Multimodal models are billed per token; the rate depends on the backend you use (set in the config).
Below is the published pricing of the default backend Luna (exchange rate 7.2 to RMB):

| Item | Per 1M tokens |
| --- | --- |
| Input | $0.20 |
| Input (cache hit) | $0.02 |
| Output | $1.20 |

> These are Luna's published unit prices, **not measured by this project**. The real cost of a single
> screenshot has not been verified by a live call yet — it will be added here once tested. Other
> backends have their own rates; fill `price_in` / `price_out` in that backend's config. If left
> blank, the script prints "price not configured" instead of guessing.

You don't have to do the maths. Every call ends with a line of real usage (numbers below are just
format illustration):

```
> 眼睛[luna/gpt-5.6-luna] · 用时 3.2s · 输入 1234 tok（缓存 0）· 输出 567 tok · 约 ¥0.0000
```

One habit that keeps it cheap: ask everything in one `-q`; don't call the script for text-only work.

## ❓ Troubleshooting

Run the self-check first. It lists all backends (model / masked key) and pings the default
one. Or just list backends without the network test:

```bash
python ~/.deepseek-eyes/see.py --check
python ~/.deepseek-eyes/see.py --list-backends
```

| Symptom | Cause and fix |
| --- | --- |
| Says there are no backends | Re-run `install.py` and add `backends` to the config |
| Says a backend has no api_key | Edit `~/.deepseek-eyes/config.json` and set `api_key` for that backend |
| HTTP 401 / 403 | Key and backend don't match (official key with a relay URL, or vice versa) |
| HTTP 404 | Wrong model name; relays usually need `/v1` at the end of the base URL |
| Connection fails or times out | Set `HTTPS_PROXY`, or switch to a relay URL if `api.openai.com` is unreachable |
| Installed but the agent never calls it | Restart the app so it reloads skills, or say "use deepseek-eyes on this image" explicitly |

<details>
<summary>Editing the config by hand</summary>

`~/.deepseek-eyes/config.json`:

```json
{
  "default_backend": "luna",
  "backends": {
    "luna":  {"api_key": "sk-xxx", "base_url": "https://api.openai.com/v1", "model": "gpt-5.6-luna"},
    "gpt4o": {"api_key": "sk-xxx", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"}
  }
}
```

Environment variables are also supported: `DEESEEK_EYES_BACKEND` picks the backend; for OpenAI-style
backends `LUNA_API_KEY` / `OPENAI_API_KEY` override the config.

</details>

## 🙏 Acknowledgements

- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) — the retina of these eyes (the OpenAI-compatible backend uses it by default)
- [DeepSeek API](https://api-docs.deepseek.com/) — the brain that does the thinking
- [Pillow](https://github.com/python-pillow/Pillow) — optional image compression

## 📄 License

MIT

<div align="center">

If this helped, drop a ⭐

</div>
