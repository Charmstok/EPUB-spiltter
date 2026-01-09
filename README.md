# EPUB-spiltter
利用大模型，将 EPUB 格式的电子书逐步处理为 slice（一个完整的小故事）。

---

# 项目功能

## Step 1: Cleaning

从 EPUB 中抽取正文并清洗为纯文本句子：删除章节划分与无效字符，过滤广告/水印，识别并分离“求月票/求订阅”等内容。

仅保留章节标题为“第xx章/回/节 xx”后的正文。

规则由 `step1_cleaning/rule/rules.json` 配置。

输出为 `book/xxx.txt`（与 epub 同名），一行一句。

基础命令：
```sh
python3 -m step1_cleaning.clean book/<这里缺个名字>.epub
```

[Step 1 的更多介绍](step1_cleaning/README.md)

---

## Step 2: Slice

将 Step 1 清洗后的正文调用大模型进行划分 slice。

### 配置文件

1. API KEY、Model等与模型相关的配置文件
2. 调用大模型时的最大回答 `max_tokens`；每次调用大模型时，输入多少字的txt小说正文等设置