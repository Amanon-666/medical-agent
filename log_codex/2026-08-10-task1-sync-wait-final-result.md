# 任务一同步等待与无总时限修正（2026-08-10）

## 用户要求

- 任务一正常对话必须等待 DataMate 和 MinerU 子任务完成，在同一轮直接返回最终结果。
- 不因预设任务总时限提前结束；明确失败仍须返回真实失败，不得伪造成功。
- 保留格式分组并发和显式 `wait=False` 后台兼容模式。

## 证据与原因

- 本地 `main` 原有实现已经把混合清洗改成后台提交，但 Nexent Agent 3 的确定性路由仍强制 `wait=False`，因此首次答复只有 `run_id`，需要第二轮状态查询。
- 服务器旧版 DataMate 轮询仍使用 900 秒总时限，MinerU 环境变量仍设置 300 秒总时限。
- Nexent 两套运行包已通过 V3 路由补丁升级为 `wait=True`；Agent 3 发布版本为 70。

## 实施

- `run_task1_mixed_cleaning` 和服务入口默认改为 `wait=True`；`wait=False` 只在调用方明确要求非阻塞时启动后台 worker。
- DataMate 和 MinerU 轮询取消任务级总时限；单次 HTTP 请求仍有连接超时，超时后继续轮询。
- Nexent V2 路由补丁可原位升级为 V3，避免重复插入旧路由；任务提示要求工具返回前不得回答。
- 部署脚本备份 `.env.runtime`，并将 `CCF_MINERU_TIMEOUT_SECONDS` 清空，防止下次部署恢复 300 秒截止时间。

## 验证

- 本地编译和回归测试：16 项通过。
- 重启后的真实 Nexent/DataMate 链路：Agent 端到端 59.277 秒，任务一工具 36.99 秒；1 次工具调用后得到 1 次最终答复，没有 `async_started`、后台处理中或二次状态查询要求。
- 真实返回最终数据集：`14ac4fc9-4a36-4a42-a3fd-6b908d04a0a9`；5 个文件、29 条记录，TXT、CSV、JSON、JSONL、PDF 五类输入均处理成功。

## 未完成或风险

- `wait=False` 后台状态工具仍保留，供明确的非阻塞调用方使用；它不是正常 Nexent 对话路径。
- 单次 HTTP 请求超时用于释放断开的网络连接，不代表 DataMate 或 MinerU 任务截止时间；平台明确失败时仍会结束并返回失败状态。
