#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deepseek-eyes 图形界面安装器（小白版）

不用碰命令行：双击运行 → 选平台 → 粘贴 key → 点「安装」。
背后复用 install.py 的底层逻辑（复制 see.py、写配置、装技能到各 agent）。
"""
import os
import sys
import types

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import install

PLATFORM_OPTIONS = [
    ("OpenAI（GPT-5.6 Luna / GPT-4o）", "openai"),
    ("阿里通义千问 Qwen-VL（DashScope）", "qwen"),
    ("智谱 GLM（BigModel）", "glm"),
    ("Google Gemini（OpenAI 兼容）", "gemini"),
    ("其他 OpenAI 兼容中转站 / 自定义", "custom"),
]
LABEL_TO_KEY = dict(PLATFORM_OPTIONS)


def run_install(plat_key, api_key, log):
    """核心安装逻辑（与命令行版一致，非交互）。log 是可调用对象，接收字符串。"""
    # 强制走非交互配置路径
    sys.stdin.isatty = lambda: False
    args = types.SimpleNamespace(
        api_key=api_key,
        yes=True,
        backend=plat_key,
        base_url="",
        model="",
        targets="",
        all=True,
        deps=False,
        uninstall=False,
    )
    log("① 复制核心脚本 see.py …")
    install.step_copy_script()
    log("② 写入配置（平台=%s）…" % plat_key)
    install.step_config(args)
    log("③ 安装技能到各 AI 客户端 …")
    install.step_install_targets(args)
    log("④ 自检 …")
    install.step_check({})


def do_install():
    plat_key = LABEL_TO_KEY.get(plat_var.get(), "openai")
    api_key = key_var.get().strip()
    if not api_key:
        messagebox.showwarning("还差一步", "请先粘贴 API key 再点安装。")
        return
    install_btn.config(state="disabled")
    try:
        def log(msg):
            text_area.insert(tk.END, msg + "\n")
            text_area.see(tk.END)
            root.update_idletasks()

        run_install(plat_key, api_key, log)
        messagebox.showinfo(
            "装好了",
            "deepseek-eyes 已安装完成。\n\n请重启你的 AI 客户端，之后直接发图片就能用。",
        )
    except Exception as e:
        messagebox.showerror("安装出错", str(e))
    finally:
        install_btn.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("deepseek-eyes 安装向导")
    root.geometry("540x440")

    tk.Label(root, text="给纯文本 AI 装上眼睛", font=("Microsoft YaHei", 15, "bold")).pack(pady=(12, 2))
    tk.Label(root, text="选平台 → 粘贴 key → 点安装，全程不用命令行。").pack()

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="x")

    tk.Label(frm, text="① 选择平台：").grid(row=0, column=0, sticky="w", pady=6)
    plat_var = tk.StringVar(value=PLATFORM_OPTIONS[0][0])
    ttk.Combobox(
        frm, textvariable=plat_var, values=[p[0] for p in PLATFORM_OPTIONS],
        state="readonly", width=42,
    ).grid(row=0, column=1, pady=6)

    tk.Label(frm, text="② 粘贴 API key：").grid(row=1, column=0, sticky="w", pady=6)
    key_var = tk.StringVar()
    ttk.Entry(frm, textvariable=key_var, show="*", width=45).grid(row=1, column=1, pady=6)

    install_btn = ttk.Button(root, text="安 装", command=do_install)
    install_btn.pack(pady=6)

    text_area = scrolledtext.ScrolledText(root, height=13)
    text_area.pack(fill="both", expand=True, padx=12, pady=8)
    text_area.insert(tk.END, "点击「安装」后，进度会显示在这里。\n")

    root.mainloop()
