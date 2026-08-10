# Nexent 运行时补丁

本目录保存 MediFlow 对 Nexent 上游运行时的最小兼容补丁。补丁用于保证任务一智能体先执行已绑定工具，再依据工具返回结果生成答复，避免模型在未调用工具时虚构排队状态、运行编号或清洗结果。

## 文件职责

| 文件 | 作用 |
| --- | --- |
| `apply_task2_llm_guardrails.py` | 为任务二的 LLM 抽取结果补充可靠性等级、空值和未知值隔离，以及 hybrid 缺少 LLM 客户端时的显式降级保护。 |
| `apply_nexent_tool_evidence_guard.py` | 记录真实工具调用证据；未执行绑定工具时禁止直接返回最终结论。 |
| `apply_nexent_task1_deterministic_route.py` | 对带明确数据集名称的“只探查”与“执行清洗”请求生成确定性任务一工具入口。 |
| `apply_all.sh` | 备份 Nexent 运行时文件、幂等应用补丁、执行语法检查并重启容器。 |

## 应用

在项目根目录执行：

```bash
bash deploy/runtime_patches/apply_all.sh
```

任务二安全补丁单独执行：
```bash
bash deploy/apply_task2_llm_guardrails.sh
```
该脚本会先备份三个任务二抽取文件，再应用补丁并进行 Python 语法检查；重启 MCP 服务后才会加载新代码。补丁只作用于本项目，不修改 DataMate 或 Nexent 上游代码。

容器名称不是 `nexent-runtime` 时，可设置 `NEXENT_RUNTIME_CONTAINER`。脚本会在 `backups/nexent_runtime_patches_<时间>/` 保存四个原始运行时文件。

## 验证

补丁应用后，在 Nexent 任务一智能体中执行：

```text
清洗数据集“糖尿病全流程PDF混合演示数据集”，任务名为PDF混合清洗验证。
```

智能体的第一项动作应为 `run_task1_mixed_cleaning(..., wait=False)`。首次答复只说明任务已提交并给出真实 `run_id`，不得提前声称完成；后台完成后调用 `get_task1_mixed_cleaning_status(run_id)` 获取最终数据集 ID 和处理指标。

## 回滚

将最近一次备份目录中的四个文件分别恢复到 Nexent 容器的原路径，执行 Python 语法检查后重启容器。补丁只修改 Nexent Python 运行时，不修改数据库和业务数据。
