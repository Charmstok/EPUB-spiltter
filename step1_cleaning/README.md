# Step 1：数据清洗（EPUB -> 纯句子）

输出格式：一行一个句子（UTF-8 文本）。

## 使用

```bash
python3 -m step1_cleaning.clean book/xxx.epub
```

默认输出到 `book/<epub文件名>.txt`。

## 可选操作

把被规则识别出的内容单独写到 JSONL（例如“求月票/求订阅”等）：

```bash
python3 -m step1_cleaning.clean book/xxx.epub --extracted-out extracted.jsonl
```

## 章节保留策略

仅保留章节名匹配 `第xx章/回/节 xx`（如 `第1章 陨落的天才`）之后的正文内容；

其它标题（如前言/后记/番外等）会被跳过。

## 规则

清洗会自动读取 `step1_cleaning/rule/rules.json`（同时包含章节识别规则与噪声过滤规则）。

### 快速开始

- 直接编辑 `step1_cleaning/rule/rules.json` 里的规则即可生效

### 规则文件格式

- `heading`：章节/标题识别规则（用于“只保留第xx章/回/节”后的正文）
- `rules`：规则列表（按顺序依次应用到“句子”）

#### heading 字段说明

- `heading.max_len`：标题行最大长度，超过则不当作标题
- `heading.digit_only`：是否把纯数字行当作标题（常见于分隔页码）
- `heading.skip_leading_titles`：遇到严格章节标题后，额外跳过开头若干行“像标题但不是标题”的短行（例如重复的章节名/卷名）
- `heading.leading_title_max_len`：上述“短行”的最大长度
- `heading.strict_chapter_title`：严格章节标题（命中则“开始保留正文”）
- `heading.generic_heading`：宽松标题识别（命中则当作标题行，用于切断/跳过）
- `heading.other_headings`：其它标题规则列表（如前言/后记/番外、英文 chapter 等）

其中 `strict_chapter_title`/`generic_heading`/`other_headings` 的每个元素支持两种写法：
- 字符串：直接作为正则 `pattern`
- 对象：`{"pattern": "...", "flags": "i|m|s(可选)" }`

#### rules 字段说明


- `name`：规则名（用于 extracted 记录）
- `kind`：`drop`（丢弃该句）/ `extract`（正文不保留，但写入 `--extracted-out`）/ `replace`（替换后继续）
- `pattern`：Python 正则表达式
- `flags`：可选，正则标志字符串（`i` 忽略大小写，`m` 多行，`s` dotall）
- `bucket`：类别标签（如 `watermark`、`solicitation`），用于下游统计/分流
- `replacement`：仅 `kind=replace` 需要
