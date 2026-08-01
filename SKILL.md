---
name: deepseek-eyes
description: 给看不见图的纯文本模型（DeepSeek V4 等）外接一副眼睛。当任务里出现图片、截图、设计稿、报错截图、图表、扫描件，或者用户说"看这张图/这个界面/这个报错/帮我复刻/提取文字/读一下数据"时，必须用本技能把图交给一个支持图片输入的多模态模型（GPT-5.6 Luna、GPT-4o、Qwen-VL，或任意 OpenAI 兼容中转站），识别成文字，再基于文字继续干活。禁止靠文件名或上下文猜测图片内容。
license: MIT
---

# deepseek-eyes：给纯文本模型外接的眼睛

你自己看不见图像。凡是需要"看"的事情，一律交给这个脚本，它会把图片发给一个
支持图片输入的多模态模型，把画面转成足够详细的文字回给你。

支持多个后端、多把 API key：在 `~/.deepseek-eyes/config.json` 里可以写一组命名后端
（每个后端各带自己的 key / 接口 / 模型），平时用默认那个，需要时换成别的模型。
图片一律以 base64 编码后发送。所有后端都走 OpenAI 兼容协议。

## 什么时候必须调用

只要满足任意一条，先调脚本，再做别的：

- 用户消息里带了图片路径、图片网址，或提到某个 `.png/.jpg/.jpeg/.webp/.gif/.bmp` 文件
- 用户说"看看这个 / 这张图 / 这个截图 / 这个界面 / 这个报错 / 这张表"
- 需要照着设计稿或界面截图写前端代码
- 需要从图表、仪表盘、扫描件、发票、论文里取数据或取文字
- 需要对比两张图的差异（改版前后、预期与实际）

**铁律：绝不根据文件名、目录名或聊天上下文编造图片内容。没调脚本就等于没看见。**

## 怎么调用

```bash
{{SEE_CMD}} <图片路径> [更多图片...] [-q "具体问题"] [--backend <后端名>]
```

`--backend <名字>` 用来选用配置里的哪个多模态后端；不写就用 `default_backend`。
例如用户明确想要另一个模型时，加 `--backend gpt4o`。

不写 `-q` 时做通用详细描述；写了 `-q` 就只回答那个具体问题（适合"右下角那个数字是多少"这类）。

常用例子：

```bash
{{SEE_CMD}} C:\shots\bug.png
{{SEE_CMD}} ./design/home.png -q "这个界面用了哪些主色，给十六进制色值"
{{SEE_CMD}} ./before.png ./after.png -q "对比这两张图的区别"
{{SEE_CMD}} ./dashboard.png --json                 # 要结构化结果时加 --json
{{SEE_CMD}} ./page.png --backend gpt4o             # 用 gpt4o 后端看
```

其他参数：`--max-side 2048`（图太糊时提高清晰度）、`--check`（自检配置和网络）、
`--list-backends`（列出已配置的后端）。

## 省钱守则

多模态模型按量计费，具体单价看你用的后端（写在配置文件里）。要守规矩：

1. **一次问全。** 调用前先想清楚需要哪些信息，写进 `-q` 一次问完，不要看一次问一句。
2. **纯文字任务不要调这个脚本。** 你自己能干的活自己干，眼睛只在需要看图时睁开。

## 拿到结果之后

脚本返回的是文字，你要把它当作"亲眼所见的事实"来用：

- 引用图中数据、报错、文案时，照抄脚本给的原文，不要转述走样
- 脚本写了"看不清 / [?]"的地方，如实告诉用户看不清，不要替它补齐
- 复刻界面时以脚本给出的组件清单和色值为准
- 若结果明显不足以支撑任务（比如图太糊），可以加 `--max-side 2048` 重看一次，最多重试一次

## 出问题时

先跑 `{{SEE_CMD}} --check`，它会列出所有已配置的后端（含模型 / key 掩码），
并试连默认后端一次。也可以用 `{{SEE_CMD}} --list-backends` 只看后端列表。

| 现象 | 原因和处理 |
|---|---|
| 提示没有任何后端 | 让用户跑一次 `install.py` 在配置里加上 backends |
| 提示某后端没配 api_key | 让用户编辑 `~/.deepseek-eyes/config.json`，在该后端里填 api_key |
| HTTP 401 / 403 | key 和后端不配套（官方 key 配了中转地址，或反过来） |
| HTTP 404 | 模型名写错，或中转站地址要带 `/v1` 结尾 |
| 连不上、超时 | 国内直连 `api.openai.com` 通常不通，可改中转地址或设代理 `HTTPS_PROXY` |

配置文件在 `~/.deepseek-eyes/config.json`（Windows 是 `C:\Users\<用户名>\.deepseek-eyes\config.json`），
结构示例：

```json
{
  "default_backend": "luna",
  "backends": {
    "luna":  {"api_key": "sk-...",  "base_url": "https://api.openai.com/v1", "model": "gpt-5.6-luna"},
    "gpt4o": {"api_key": "sk-...",  "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
    "qwen":  {"api_key": "sk-...",  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-vl-max"}
  }
}
```

想用 Gemini：把 `base_url` 填成它的 OpenAI 兼容地址（形如 `https://generativelanguage.googleapis.com/v1beta/openai`），模型写 `gemini-2.0-flash`。
想用 Claude：走一个 OpenAI 兼容中转站，把 key 和地址填进对应后端即可。
