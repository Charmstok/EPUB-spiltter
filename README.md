# EPUB-spiltter
利用大模型，将 EPUB 格式的电子书逐步处理为 slice（一个完整的小故事）。

---

# 项目功能

## Step 1: Cleaning

### 介绍

从 EPUB 中抽取正文并清洗为纯文本句子：删除章节划分与无效字符，过滤广告/水印，识别并分离“求月票/求订阅”等内容。

仅保留章节标题为“第xx章/回/节 xx”后的正文。

### 配置文件

规则由 `step1_cleaning/rule/rules.json` 配置。

### 输出

输出为 `book/xxx.txt`（与 epub 同名），一行一段。

### 快速开始

基础命令：
```sh
python3 -m step1_cleaning.clean book/<这里缺个名字>.epub
```

> [Step 1 的更多介绍](step1_cleaning/README.md)

---

## Step 2: Slice

### 介绍

将 Step 1 清洗后的正文调用大模型进行划分 slice（每个 slice 约 5000～6000 字，按“句子边界”切分）。

### 配置文件

1. 多家模型 API（Provider / Base URL / API Key / Model 等）
2. 切分参数（slice 字数范围、每次请求输入约 14000 tokens、失败重试次数等）

### 输出

默认输出到 `book/<小说同名>_slice/<时间戳>/slices.json`。

### 快速开始

请先设置自己的环境变量，例如 config/llm.json 中的 VOLC_ARK_API_KEY

```sh
export VOLC_ARK_API_KEY='你的key'
```

```sh
python3 -m step2_slice.slice book/xxx.txt
```

只切分前 N 个 slice：
```sh
python3 -m step2_slice.slice book/xxx.txt --max-slices 20
```

> [Step 2 的更多介绍](step2_slice/README.md)
