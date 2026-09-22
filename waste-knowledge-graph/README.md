# 垃圾分类知识图谱的构建及可视化

> 报告目录已整理：当前说明和归档索引见 [reports/README.md](reports/README.md)。历史日志、评测和截图已按用户选择清理；当前网页实验结果读取 `models_manual/` 内与模型权重对应的评测文件。


依据 `sb.docx` 实现的 Python 课程项目，包含 Scrapy 爬虫、数据清洗、TensorFlow BiLSTM-CRF、BiGRU-Attention、模型训练评估、Neo4j 导入和中文查询界面。

项目采用上海四分类：**可回收物、干垃圾、湿垃圾、有害垃圾**。“可回收垃圾”作为“可回收物”的查询别名。目录为典型物态的教学示例；不自动把模型猜测写成分类事实。

## 2026年9月15日数据集迭代

已接入用户提供的外部分类表 `garbage_cleaned.csv`、`garbage_cleaned.jsonl` 与 `garbage_cleaned_with_method.jsonl`，三者均为3712条、名称与类别一致的同一份数据（带方法的那份按类别补充投放方法），已合并为 `data/garbage_cleaned_merged.jsonl`。归一化后共3710个物品、3718个节点、7420条关系（每条物品各有分类关系和投放关系）。系统运行时只读取 `data/garbage_cleaned_merged.jsonl` 这一份数据源，不再读取 `catalog.json`、`imported/`；原134条教学目录不再进入运行时查询与图谱。

- “厨余垃圾 → 湿垃圾”“其他垃圾 → 干垃圾”仅做名称映射；外部数据没有地区信息，不能视为已满足上海实际规则。
- 外部标签标记为 `source_labeled`，逐条保留原名称、类别、来源行号和链接；不标记成人工审核通过。
- 87组与原目录同名同类，2条规范化重复归并；“竹签”的1组分类冲突隔离，保留原目录，不进入新训练集。
- 所有新数据缺少描述与投放方法，因此只生成分类关系，不自动补造 `DISPOSE_WITH`。
- 页面增加来源筛选、12/24/48条可选分页、证据问答和数据质量审计；图谱与列表同步翻页，快速切换查询不再被旧响应覆盖。

原始输入、原训练集和原模型均保留。新增3622条已正式合并到 `data/catalog.json`，主目录共3756条；原134条目录完整备份为 `data/catalog.before_external_merge.json`。来源审计目录为 `data/imported/`，新实验语料为 `data/processed_external/`，新权重为 `models_external/`。

### 图谱布局修复与查看方式

图谱已改为类别、物品卡片、投放方法的分层布局，完整名称自动换行，不再挤在固定小圆环中。默认每页12个物品，图谱与下方列表使用同一页；可改为24或48个。支持缩放、拖动画布、拖动节点、适应全部、重置布局和展开大图；按Escape退出大图。大图只显示当前页，使用分页浏览全部3756条，不会一次堆叠全部节点。

窄屏长图默认保留可读字号，通过画布滚动查看，不再强行缩小整图；窗口宽度变化时自动重排。适应全部切换为本页全景，重置布局恢复清晰滚动视图。本次补测34项数据/接口测试通过，7项前端测试连续三轮通过，390与1400宽度的SVG渲染已检查。仅更新静态页面时按Ctrl+F5即可；后端代码变更时仍需按下述方式重启。

**已有服务必须先在原终端按Ctrl+C停止，再重新运行 `start.cmd`，浏览器按Ctrl+F5刷新。** 只刷新浏览器不能替换旧进程中的后端分页代码。

本次55项Python测试分组通过、5项前端DOM测试通过；实际SVG渲染已检查，无标签重叠或节点裁切，但当前环境没有可连接的浏览器，未做完整浏览器截图验收。更大范围合并测试仍触发过本机Python 3.11原生访问异常，不宣称运行时问题已修复。详见 《图谱布局与数据合并说明.md》（历史材料已清理）。

### 重现数据接入

```powershell
python -m wastekg.dataset data/garbage_cleaned_merged.jsonl --merge-catalog
python -m wastekg.graph
```

CSV与JSONL任选一种作为主输入；另一种用于一致性核验。命令可重复执行，更新派生产物但不修改原文件。人工调整原目录后，应重新执行接入、构图并重启服务。

### 独立训练及评估

```powershell
python -m wastekg.train --data-dir data/processed_external --output models_external --epochs 3 --balance-relations
python -m wastekg.web_eval --model-dir models_external --output models_external/web_metrics.json
python -m wastekg.challenge --model-dir models_external --output models_external/challenge_metrics.json
```

生成训练15938句、验证3416句、测试3442句；按规范物品名分组隔离，字表只由训练集生成。它们是由分类标签合成的弱监督模板，并非真实网页BIO人工标注。关系类别采用可选的逆平方根频率加权，缓解投放关系样本少的问题。

**新模型只作为实验产物，不替换默认模型。** 本轮3轮训练在模板测试集的实体F1为99.97%、关系宏F1为100%，但网页与改写集端到端F1均为0；原模型在同环境复测分别为6.45%、48%。这说明模板高分不等于泛化提升，不能用这些结果宣称实用性提高。后续需要真实语句标注、独立来源留出集及更丰富的句式，再决定是否替换模型。

默认 `start.cmd` 使用 `models_manual` 模型和扩展目录；若需要查看新模型实验，可运行 `start.cmd --model-dir models_external`。评测文件绑定模型权重与字表指纹，重训后须重新评测，不能挪用旧分数。浏览器“实验与评估”展示当前选择模型的结果。

### 本轮验证

Python回归测试与前端DOM测试命令如下。前端测试需Node.js和一个运行在18765端口的本地服务，不是浏览器截图验收。

```powershell
python -m pytest -q --junitxml=reports/tests_iteration.xml
python -m wastekg.server --port 18765 --model-dir models_external
# 在另一终端执行
npm ci
npm test
```

本轮53项Python测试曾整套通过并按文件复测通过，3项前端DOM测试通过。但本机Python 3.11在重复运行时出现间歇性原生访问异常，关闭oneDNN也未完全消除；不能宣称本机运行时已稳定，正式演示前需在干净的Python 3.12环境复验。测试进程默认关闭oneDNN，训练和服务配置不变。详细结果、限制和验收步骤见 《迭代验收说明.md》（历史材料已清理）。本机已在仓库上一级的 `.venv` 中安装依赖，`start.cmd` 会自动识别；手动执行可用 `..\.venv\Scripts\python.exe` 替换命令中的 `python`。

## 先运行演示

需要 Python 3.11 或 3.12（本轮使用3.11）。在本目录打开终端：

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
| `models_manual/` | 两个模型权重、字表、逐轮日志和最终指标 |
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

`prepare` 会重建教学目录与模板数据，覆盖此前对目录的手工修改，修改前请备份。训练会更新 `models_manual/`，Web 服务会显示训练进度，训练完成后再恢复神经抽取。也可以用 `--output models_new` 保存到其他目录。随机种子为 42；不同硬件或 TensorFlow 内核可能存在数值差异。

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

打开 **http://localhost:7474**，连接本机 Neo4j，执行 `neo4j/queries.cypher` 中的语句查看图谱。所有节点有 `WasteKGEntity` 标签，并通过 `kind` 属性区分 ITEM、CATEGORY、METHOD。导入使用唯一约束、MERGE 和参数，不删除既有数据库数据；再次导入不会创建重复节点或关系。默认包含标记为 `source_labeled` 的外部关系，若只导入原目录可加 `--teaching-only`。此参数不删除历史上已导入的外部关系；需要纯教学视图时应按审核状态筛选。当前 《neo4j_import.json》（历史材料已清理） 是旧版134条目录的历史导入记录，不是此次扩展图谱已入库的证明。本轮Docker服务未运行，未执行真实Neo4j导入。

本地 Web 图谱读取 JSON；Neo4j 的真实可视化在 Neo4j Browser 中展示，二者不可混称。数据库服务仅映射本机端口。停止本项目容器使用 `docker compose -p wastekg-course stop`，保留数据库卷。

## 接口

| 接口 | 功能 |
|---|---|
| `GET /api/stats` | 目录规模、来源与模型文件状态 |
| `GET /api/search?q=香蕉皮&category=湿垃圾&limit=24&offset=0&scope=all` | 分页查询；scope支持all、teaching、external；单页最多150条 |
| `GET /api/graph?q=香蕉皮` | 关联子图 |
| `GET /api/metrics` | 主实验及额外评测结果 |
| `GET /api/qa?q=阿司匹林是什么垃圾` | 明确物品的证据问答，未知与模糊物态不自动推断 |
| `GET /api/dataset` | 双格式一致性、来源、类别分布与冲突摘要 |
| `POST /api/extract` | JSON 请求，字段 `text` 与 `mode`，mode 为 neural 或 baseline |

服务只监听 `127.0.0.1`，适合个人课程演示，不是多用户生产服务。没有登录、权限管理或公网部署能力。

## 来源与许可

分类来源见 `data/sources.json`，新增数据处理与验证结果见 《迭代验收说明.md》（历史材料已清理）。采集文本和外部分类表需保留原来源及许可；外部分类表的许可尚未核实，不能因项目采用MIT就视作允许任意分发。原创项目代码采用MIT，数据和依赖的许可不因此改变。原权重使用教学语料，新实验权重使用标签生成的弱监督语料，均未使用第三方预训练模型。

## 更新默认模型与网页训练记录

在项目目录使用已安装 TensorFlow 的 Python 执行以下命令（PowerShell 中 `$pythonExe` 为该解释器路径）：

```powershell
& $pythonExe -u -m wastekg.train --data-dir data/processed_retrain_20260922 --output models_manual --epochs 12 --batch-size 96 --balance-relations
& $pythonExe -m wastekg.challenge --model-dir models_manual --output models_manual/challenge_metrics.json
& $pythonExe -m wastekg.web_eval --model-dir models_manual --output models_manual/web_metrics.json
```

`--output models_manual` 覆盖网站默认模型；指定其他目录是独立实验，不会自动替换默认模型。每次训练生成唯一批次、开始和完成时间，按轮次覆盖 `models_manual/history.json`，完成后覆盖主实验指标。`models_manual/training_run.json` 记录批次与进度，批次数从启用该记录机制后开始计数。训练进行中或中断时不展示上一批的评测；重新执行训练会开始新批次。旧挑战集和网页评测若与新权重不匹配会隐藏，完成上面两个评测命令后显示新结果。

实验页每 10 秒检查最新记录，也可点击“刷新训练结果”。图中标注训练轮次及 F1，表格展示原始逐轮数值和最佳轮次。相同数据及随机种子可重复得到相同数值，批次与时间用于区分训练，不人为修改指标。抽取接口在训练完成后自动重新加载变化的模型权重。
