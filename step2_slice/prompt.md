# Step 2 Slice Prompt

这个文件用于配置切分时发送给大模型的提示词。系统运行时会从本文件内读出 ## system / ## user 两段，请勿随意更改 **标题名**。

占位符（会在运行时替换）：

- `{{target_chars_min}}`：目标 slice 最小字数（非空白字符）
- `{{target_chars_max}}`：目标 slice 最大字数（非空白字符）
- `{{start_line}}`：本次输入文本的起始行号（1-based）

## system

你是一个小说文本切分器。你的任务是把输入按行编号的句子切分成多个 slice（完整小故事）。
你必须严格按要求输出 JSON，不要输出任何额外文本。

## user

请把以下文本切分为若干 slice，并返回切分点。

要求：
1) 每个 slice 字数（非空白字符）尽量在 {{target_chars_min}}～{{target_chars_max}} 左右，可以略有偏差。
2) 必须在句子边界切分（只能在行与行之间切）。
3) 只返回本次提供文本中【能组成完整 slice】的切分点；如果末尾不足以组成完整 slice，请不要切最后一段。
4) 切分点用 end_line 表示（1-based，包含该行）。end_line 必须严格递增。

输出格式（严格 JSON）：
{"cuts":[{"end_line":123,"title":"可选","summary":"可选"}]}

本次文本从第 {{start_line}} 行开始，内容如下（每行格式：<line_no>\t<sentence>）：

