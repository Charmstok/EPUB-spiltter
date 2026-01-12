# Step 2：Slice（纯文本行 -> slice JSON）

输入：Step 1 的输出 `book/<小说名>.txt`（一行一段，UTF-8）。

输出：`book/<小说名>_slice/<时间戳>/slices.json`（JSON 数组）。

## 目标

- 每个 slice 约 **5000～6000 字**（按“非空白字符”统计）
- **必须在行边界切分**（即 Step 1 文本的行边界）
- 允许跨章节（Step 1 已经不保留章节概念）
- 每次请求大模型输入约 **14000 tokens**（可配置）
- 失败重试默认 **5 次**（可配置）

## 快速开始

1) 准备 Step 1 的文本：

```bash
python3 -m step1_cleaning.clean book/xxx.epub
```

2) 配置 Step 2

本步骤有 2 个配置文件（请从 example 复制一份再改）：

- `step2_slice/config/llm.json`：多家模型 API 配置（provider/base_url/api_key/model）
- `step2_slice/config/slice.json`：切分参数（slice 字数范围、chunk 输入 tokens、失败重试等）

示例文件：
- `step2_slice/config/llm.example.json`
- `step2_slice/config/slice.example.json`

3) 运行切分：

```bash
python3 -m step2_slice.slice book/xxx.txt
```

## 可选操作

只切分前 N 个 slice（默认不限制，切完整本书）：

```bash
python3 -m step2_slice.slice book/xxx.txt --max-slices 20
```

## 配置说明

### 1) `llm.json`（多家 API）

按 provider 名称配置（用于 failover）：

- `type`：`volc_ark` 或 `openai_compatible`
- `base_url`：例如 `https://ark.cn-beijing.volces.com`
- `api_key_env`：推荐用环境变量（避免把 key 写进文件）
- `model`：模型或 Endpoint ID

### 2) `slice.json`（切分参数）

常用字段：

- `target_chars_min` / `target_chars_max`：每个 slice 的字数范围（默认 5000/6000）
- 说明：该范围为“目标范围”，程序会尽量贴近，不严格强制在区间内
- `chunk_input_tokens`：每次喂给模型的小说正文 token 预算（默认 14000，使用启发式估算）
- `completion_max_tokens`：模型回答最大 token（只需返回切分点 JSON，建议较小）
- `retry_max`：失败重试次数（默认 5）
- `provider_order`：按顺序尝试的 provider 列表（例如 `["volc", "openai"]`）

## 输出 JSON 格式

默认输出为 JSON 数组（每个元素一个对象），字段示例：

- `slice_id`：从 1 开始递增
- `start_line` / `end_line`：对应原 txt 的行号（1-based）
- `char_len`：slice 字数（非空白字符）
- `text`：slice 正文（按原 txt 一行一段，用 `\n` 拼接）
- `title` / `summary`：可选（由模型返回）
- `error`：仅在失败时出现（错误信息）

元信息与运行状态请查看同目录下的 `run.json`（包含 `source_txt/created_at/provider_order/providers_used/models_used/status/error` 等）。

提示词（发送给大模型的 prompt）在 `step2_slice/prompt.md`，可按需自行调整。

注意：如果大模型调用失败/返回无法解析/返回的切分点不可用，本次运行会停止，并在 `slices.json` 末尾追加一个包含 `error/start_line/end_line` 的对象。
同时会在终端（stderr）输出错误摘要，并以非 0 退出码结束。
