# 配置说明

本项目提供两类配置模板：

| 文件 | 用途 |
| --- | --- |
| `.env.example` | Shell 脚本、Python 脚本和服务运行时读取的环境变量模板。 |
| `config.example.yaml` | 结构化配置示例，说明服务地址、账号、数据库和部署路径的对应关系。 |

在线服务已经部署完成，普通验证无需填写配置文件。只有在新环境部署或接管服务时才需要复制模板并填写。

## 1. 在线服务地址

| 服务 | 地址 |
| --- | --- |
| 医学数据智能体可视化平台 | `https://demo.mashiro.xin/` |
| Nexent 智能体平台 | `https://nexent.mashiro.xin/` |
| DataMate 数据处理平台 | `https://datamate.mashiro.xin/` |

演示账号：

```text
账号：suadmin@nexent.com
密码：241002814
```

## 2. 必填配置

新环境部署时，至少需要填写：

| 字段 | 说明 |
| --- | --- |
| `CCF_NEXENT_CONFIG_BASE` | Nexent 配置接口地址。 |
| `CCF_NEXENT_RUNTIME_BASE` | Nexent 运行时接口地址。 |
| `CCF_NEXENT_EMAIL` / `CCF_NEXENT_PASSWORD` | Nexent 管理员账号。 |
| `CCF_DATAMATE_BASE` | DataMate API 地址。 |
| `CCF_MCP_URL` | Nexent 访问 MCP 服务的地址。 |
| `CCF_TASK3_DEMO_URL` | 可视化平台公网地址。 |
| `CCF_DATAMATE_OPERATOR_VOLUME` | DataMate 算子运行目录。 |
| `CCF_DATAMATE_RUNTIME_CONTAINER` | DataMate 算子运行容器名。 |

## 3. 可选配置

| 字段 | 说明 |
| --- | --- |
| `CCF_LLM_API_KEY` | 模型增强抽取或智能体调用需要时填写。 |
| `CCF_EMBED_API_KEY` | 向量知识库或语义检索扩展需要时填写。 |
| `CCF_DEMO_DELETE_TOKEN` | 可视化平台启用数据来源删除功能时填写。 |
| `CCF_MCP_PUBLIC_URL` | MCP 服务需要公网访问时填写。 |

## 4. 安全注意

- 不要把真实生产密码写入 Git 历史。
- 在线演示账号只用于当前演示环境。
- 新环境部署时应替换账号、密码、域名和数据库路径。
- 数据来源删除令牌应只提供给维护人员。
