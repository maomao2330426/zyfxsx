# 报告目录说明

整理日期：2026-09-22。按用户最终选择，仅保留当前需要的报告；历史归档已清空。

## 当前保留的材料

| 文件 | 用途 |
| --- | --- |
| [标注与审核指南.md](标注与审核指南.md) | 语料标注、候选知识审核的操作说明 |
| [投放要求与句式扩展说明.md](投放要求与句式扩展说明.md) | 当前投放要求及其他句式覆盖的说明 |
| [sentence_coverage_api_cases.json](sentence_coverage_api_cases.json) | 句式扩展时保存的接口验证结果；不是新模型的独立评测 |
| [tests_sentence_coverage_python312.xml](tests_sentence_coverage_python312.xml) | 句式扩展时保存的 Python 3.12 测试记录 |
| [manual_model_activation.json](manual_model_activation.json) | 此前手动模型覆盖旧默认目录的记录；当前训练状态以 models_manual/training_run.json 为准 |
| [manual_active_server.log](manual_active_server.log) | 当前服务的标准输出日志，服务运行时可能继续写入 |
| [manual_active_server.stderr.log](manual_active_server.stderr.log) | 当前服务的错误输出日志，服务运行时可能继续写入 |

## 当前页面使用的训练与评测结果

“实验与评估”当前从默认模型目录 `../models_manual/` 读取：

- [metrics.json](../models_manual/metrics.json)：主实验指标。
- [history.json](../models_manual/history.json)：训练过程记录。
- [challenge_metrics.json](../models_manual/challenge_metrics.json)：挑战集评测。
- [web_metrics.json](../models_manual/web_metrics.json)：网页语料评测。

默认目录现已统一为 `models_manual`。训练尚未完成时，评测文件可能不存在；完成训练及对应评测命令后生成。网页只展示与当前训练及权重对应的评测。

## 文件生成位置

历史日志、旧测试、截图和旧说明已按用户选择移除。当前训练记录及评测默认写入 `models_manual/`；测试与 Neo4j 导入命令仍可在 `reports/` 生成新的记录。
