# genshinKG / genshin_impact_knowledge_graph

一个围绕《原神》数据构建知识图谱（Neo4j），并提供可视化与问答交互界面的项目。

> Pipeline：爬虫采集（srccrawler） → 数据清洗/关系抽取（data_preprocess） → Neo4j 入库 → 可视化问答（genshin_knowledge_graph）

---

## 功能概览

- 🕷️ **数据爬取**：基于 Scrapy 爬取原始数据（文本/页面结构化结果）。
- 🧹 **数据清洗 & 关系抽取**：清洗原始数据，抽取实体与关系，生成待入库数据集。
- 🧠 **知识图谱存储**：通过脚本将实体/关系写入 Neo4j。
- 💬 **可视化 + 问答交互**：在 UI 中对图谱进行查询、展示与交互式问答。

---

## 目录结构

```text
.
├── srccrawler/                  # 数据爬虫与原始数据（Scrapy 项目）
│   └── data/                     # 爬虫产出的原始数据
├── data_preprocess/              # 数据清洗、关系抽取、以及 Neo4j 入库脚本
│   ├── 其他脚本                    # 数据清洗、关系抽取、Neo4入库脚本
│   ├── (LLM_extracted)           # 经过LLM处理后的数据
│   ├── (dataKG)                  # 清洗后待入库的实体与关系数据
│   └── (dataExternal)            # 外部数据源
├── genshin_knowledge_graph/      # 图谱可视化与问答交互界面
├── schema_KG.json5               # 知识图谱 schema 定义（实体/关系/属性）
├── requirements.txt              # Python 依赖
└── README.md
