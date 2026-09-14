# 垃圾分类知识图谱的构建及可视化

依据 `sb.docx` 实现的 Python 课程项目，包含 Scrapy 爬虫、数据清洗、TensorFlow BiLSTM-CRF、BiGRU-Attention、模型训练评估、Neo4j 导入和中文查询界面。

项目采用上海四分类：**可回收物、干垃圾、湿垃圾、有害垃圾**。“可回收垃圾”作为“可回收物”的查询别名。目录为典型物态的教学示例；不自动把模型猜测写成分类事实。

## 先运行演示

需要 Python 3.12。在本目录打开终端：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m wastekg.server
```

打开 **http://127.0.0.1:8765**。Windows 也可先运行 `setup.ps1` 配置环境，再双击 `start.cmd`。关闭服务终端或按 Ctrl+C 停止。端口占用时使用 `python -m wastekg.server --port 8766`。

Linux/macOS 对应命令：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m wastekg.server
```

已附训练权重，安装依赖后可直接使用神经网络抽取；目录查询和 SVG 图谱本身只依赖 Python 标准库。没有安装 TensorFlow 时，神经网络页会明确提示，不能冒充模型已运行。界面不依赖 CDN。首次加载模型通常需数秒。

建议先试：查询“快递纸箱”，输入“香蕉皮属于湿垃圾。”进行神经网络抽取，再输入“香蕉皮不是干垃圾。”验证否定句处理。实验页显示实际保存的指标；图谱节点可拖动并点击查看详情。

## 项目目录

| 路径 | 内容 |
|---|---|
| `wastekg/prepare.py` | 教学目录、标注模板、按垃圾名称隔离的数据集与训练字表 |
| `wastekg/crawl.py` | 限域 Scrapy 采集、去重和噪声过滤、来源记录 |
| `wastekg/models.py` | BiLSTM、CRF 前向与 Viterbi、BiGRU、位置特征和 Attention |
| `wastekg/train.py` | 训练、验证集选模、测试集评估、错误案例 |
| `wastekg/inference.py` | 模型推理、显式词典规则基线、批量候选抽取 |
| `wastekg/review.py` | 逐条审核、冲突检查、目录合并与备份 |
| `wastekg/graph.py` | 稳定节点标识、本地图谱与 Neo4j 幂等导入 |
| `wastekg/server.py`、`web/` | 本地接口、四个中文功能页面 |
| `data/` | 目录、来源、采集语料、标注集、图谱与候选 |
| `models/` | 两个模型权重、字表、逐轮日志和最终指标 |
| `reports/` | 项目报告、运行记录、额外评测与测试结果 |
| `tests/` | 算法、数据、爬虫、接口与审核测试 |

## 重现采集和清洗

以下命令使用已安装依赖的 Python；Windows 可用 `.\.venv\Scripts\python.exe` 替代 `python`。先激活环境也可以。

```bash
python -m wastekg.crawl
python -m wastekg.crawl --clean data/raw/pages.jsonl data/processed/web_sentences.jsonl
```

`data/seed_urls.txt` 包含两篇百科页面和上海官方指引。爬虫遵循 robots.txt，限并发和请求间隔，保存来源 URL、采集时间、页面哈希、正文句子和失败原因。原始 HTML 不作为交付必需文件；可重新采集。百科内容存在历史信息和编辑误差，不等同于当前分类依据。

`web_sentences.jsonl` 为未逐条审核的网页句子，**不会自动作为监督训练金标准，也不会自动覆盖目录**。真实训练数据须按同一实体跨度格式标注，并以来源页面或实体组进行隔离。标注指南见 `reports/标注与审核指南.md`。

## 训练与评估

```bash
python -m wastekg.prepare
python -m wastekg.train --epochs 24
python -m wastekg.challenge
python -m wastekg.web_eval
python -m pytest -q --junitxml=reports/tests.xml
```

`prepare` 会重建教学目录与模板数据，覆盖此前对目录的手工修改，修改前请备份。训练会更新 `models/`，请先停止 Web 服务。也可以用 `--output models_new` 保存到其他目录。随机种子为 42；不同硬件或 TensorFlow 内核可能存在数值差异。

主测试集是**模板语料**，按物品名称分组隔离，字表只从训练集拟合。其高分不能代表自然网页表现。改写挑战集用于检查泛化弱点，曾用于指导数据增强方向；它是开发诊断集，不能宣称为完全盲测。网页评测集仅为少量单人标注原句，同样不足以得出生产可用结论。报告分别给出实体严格 F1、使用金标准实体位置的关系分类指标、端到端三元组指标。

## 从文本到候选与审核

```bash
python -m wastekg.inference "香蕉皮属于湿垃圾。"
python -m wastekg.inference "香蕉皮属于湿垃圾。" --baseline
python -m wastekg.inference --input data/processed/web_sentences.jsonl --output data/candidates.jsonl
```

单句限制 128 字，批量任务按句末标点切分，超长分句跳过，不截断实体。神经网络阈值为 0.8。关系 Softmax 分数未经校准，不能解释为事实正确率。

逐条阅读 `data/candidates.jsonl`，在本地建立决策文件，每行是一个 JSON：

```json
{"id":"从候选文件复制实际id","approved":true,"reviewer":"实际审核者姓名","note":"已核对原页面、地区、物态和句子极性"}
```

```bash
python -m wastekg.review data/candidates.jsonl data/decisions.jsonl --merge
python -m wastekg.graph
```

合并会生成目录备份；类别冲突会拒绝写入。审核人不能留空。重新启动 Web 服务后查询目录。新增条目还可再次导入 Neo4j。

## Neo4j 运行与可视化

安装并启动 Docker Desktop，然后在 PowerShell 中运行：

```powershell
$env:NEO4J_PASSWORD = '请替换为本机数据库密码'
docker compose -p wastekg-course up -d
.\.venv\Scripts\python.exe -m wastekg.graph --neo4j
```

首次启动需等待数据库就绪，再执行导入。默认 URI 为 `bolt://localhost:7687`，用户名为 `neo4j`，数据库为 `neo4j`；可分别设置 `NEO4J_URI`、`NEO4J_USER`、`NEO4J_DATABASE`。密码只从环境读取，源码不保存实际密码。

打开 **http://localhost:7474**，连接本机 Neo4j，执行 `neo4j/queries.cypher` 中的语句查看图谱。所有节点有 `WasteKGEntity` 标签，并通过 `kind` 属性区分 ITEM、CATEGORY、METHOD。导入使用唯一约束、MERGE 和参数，不删除既有数据库数据；再次导入不会创建重复节点或关系。数据规模见 `reports/neo4j_import.json`。

本地 Web 图谱读取 JSON；Neo4j 的真实可视化在 Neo4j Browser 中展示，二者不可混称。数据库服务仅映射本机端口。停止本项目容器使用 `docker compose -p wastekg-course stop`，保留数据库卷。

## 接口

| 接口 | 功能 |
|---|---|
| `GET /api/stats` | 目录规模、来源与模型文件状态 |
| `GET /api/search?q=香蕉皮&category=湿垃圾` | 名称和类别筛选 |
| `GET /api/graph?q=香蕉皮` | 关联子图 |
| `GET /api/metrics` | 主实验及额外评测结果 |
| `POST /api/extract` | JSON 请求，字段 `text` 与 `mode`，mode 为 neural 或 baseline |

服务只监听 `127.0.0.1`，适合个人课程演示，不是多用户生产服务。没有登录、权限管理或公网部署能力。

## 来源与许可

分类依据和论文链接见 `reports/项目报告.md`。采集的维基百科文本需保留页面归属与 CC BY-SA 等原许可；政府网页文本保留来源。原创项目代码采用 MIT，数据和第三方模型依赖不因此变更其原有许可。这里训练的权重只在所附教学语料上训练，没有使用第三方预训练模型。
