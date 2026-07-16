# AGENTS.md

本文件是 TinyDB 仓库的 AI 协作治理说明。所有自动化代理、Codex 会话和生成的计划文档都必须先遵守本文件，再进入具体代码、测试或文档工作。

## 项目定位

TinyDB 是一个从零构建的 Python 嵌入式关系型数据库，目标是在保持实现简洁、可读、可教学的同时，提供可在实际项目中嵌入使用的数据库库。

项目核心能力范围：

- 通过纯 SQL 字符串接口使用，例如 `db.execute("SELECT ...")`。
- 支持 `CREATE TABLE`、`DROP TABLE`、`INSERT`、`SELECT`、`UPDATE`、`DELETE`。
- 支持 `WHERE` 条件过滤、`AND` / `OR`、`ORDER BY`、`LIMIT`、`OFFSET`。
- 支持 `PRIMARY KEY`、`NOT NULL`、`UNIQUE` 列约束。
- 支持 `COUNT`、`SUM`、`AVG` 与 `GROUP BY`。
- 支持 `INT`、`FLOAT`、`TEXT`、`BOOL` 类型系统。
- 支持 B-tree 索引、单文件磁盘持久化、ACID 事务和 CLI/REPL。

明确不在当前范围内：

- 多表 `JOIN` 查询。
- 多线程或多进程并发安全。
- `ALTER TABLE`、视图、触发器、外键。
- 网络服务或客户端-服务器模式。

## Spec Workflow

本仓库使用 `spec-superflow` 作为唯一 AI 开发工作流。

在缺少本地框架指南或未生成对应 artifact 时，不得凭印象跳过阶段、补写隐含需求或直接扩大实现范围。若后续引入更完整的 `spec-superflow` 本地指南，应更新本文件，使仓库治理与实际 artifact 保持一致。

标准 artifact 约定：

- `changes/<change-name>/proposal.md`：需求动机、变更范围和影响，是变更意图的来源。
- `changes/<change-name>/specs/*/spec.md`：可验证需求，是行为边界的来源。
- `changes/<change-name>/design.md`：架构、模块划分、数据流和关键取舍的来源。
- `changes/<change-name>/tasks.md`：实现拆分和进度记录的来源。
- `changes/<change-name>/execution-contract.md`：获准进入构建阶段后的执行合同。
- `changes/<change-name>/.spec-superflow.yaml`：若存在，用于记录状态机和工作流元数据。

阶段顺序：

1. `exploring`：澄清目标、边界、非目标和成功标准。
2. `specifying`：形成 proposal 与可验证 spec。
3. `bridging`：形成 design、tasks 与 execution contract。
4. `approved-for-build`：等待用户批准构建。
5. `executing`：按 execution contract 实现。
6. `debugging`：遇到测试失败、行为异常或实现阻塞时进入根因分析。
7. `closing`：验证、总结、归档或合并。
8. `abandoned`：用户明确放弃或关闭该变更。

硬性规则：

- 没有 `execution-contract.md` 或没有用户批准时，不得开始实质实现。
- 需求范围变化时，必须回到 `specifying` 或 `bridging`，不能把新范围塞进执行阶段。
- 执行阶段发现 contract 与 proposal 意图不一致时，先暂停并标记 drift，再修复 artifact。
- 生成的 spec、design、tasks 和 execution contract 都必须服从本文件。

## 阅读顺序

1. 读取根目录 `AGENTS.md`。
2. 读取当前变更目录下的 `proposal.md`、`specs/*/spec.md`、`design.md`、`tasks.md` 和 `execution-contract.md`。
3. 读取与任务相关的代码、测试、文档和 CLI 入口。
4. 读取用户提供的外部材料；外部材料默认只读，除非用户明确要求同步或迁移进仓库。

## 目录职责

以下目录在项目脚手架建立后按职责维护：

- `changes/`：`spec-superflow` 变更 artifact，不存放临时代码。
- `tinydb/`：Python 包源码，包含公共 API、SQL 解析、执行器、存储引擎、索引、事务和类型系统。
- `tests/`：自动化测试，覆盖 SQL 行为、存储格式、事务语义、索引语义和 CLI。
- `docs/`：长期设计说明、使用示例和面向用户的说明文档。
- `scripts/`：开发、验证或维护脚本；脚本必须跨平台友好，Linux 环境可运行。

若目录尚未创建，不要为了满足目录清单而创建空目录；只在对应 artifact 或实现任务需要时创建。

## 实现约束

- 运行时目标是 Python，当前需求要求零外部运行时依赖。
- 公共 API 以 `db.execute("SQL ...")` 为核心，不能绕过 SQL 语义直接暴露内部存储细节。
- `.db` 单文件格式属于用户数据格式；任何格式变更都必须有测试说明兼容性影响。
- 事务实现必须明确选择 WAL、影子分页或其他方案，并在 design 中说明原子性、一致性、隔离边界和持久性保证。
- B-tree 索引必须有独立的结构不变量测试，不能只依赖查询结果间接覆盖。
- CLI/REPL 必须复用 Python API，不得维护独立执行路径。

## Linux 兼容性

- 所有文本文件使用 UTF-8、LF 换行、末尾保留一个换行符，不保留行尾空白。
- 不要在源码、配置、测试或文档示例中硬编码 Windows 盘符、反斜杠路径或大小写不敏感文件名假设。
- 路径处理使用 `pathlib` 或等价标准库 API。
- Shell 脚本必须有合适 shebang，并能在 Linux 环境执行；需要可执行权限时使用 Git 权限位记录。
- 面向 Linux 的发布包、压缩包或 CLI 入口必须在 Linux、WSL、Docker 或 CI 中验证。

## 安全与敏感信息

- 不得把固定密码、令牌、API Secret、私钥、真实生产主机、真实客户连接串或含凭据的数据库 URL 写入仓库。
- 示例凭据必须使用占位符、环境变量、配置注入或运行时生成值。
- 测试可以在内存中生成临时凭据，但不能写入可复用的硬编码密码。
- 生成 artifact 中若出现固定凭据，按计划 drift 处理并修复后再继续。

## 验证

在项目脚手架建立前，没有固定构建命令。引入 `pyproject.toml` 或等价工具后，应在本节补充仓库实际命令。

默认验证方向：

- `python -m compileall tinydb tests`
- `python -m pytest`
- CLI/REPL 冒烟测试
- 存储文件读写、事务回滚、索引一致性和 SQL 解析错误路径测试

若当前任务无法运行完整验证，必须说明原因、已运行的替代检查和剩余风险。

## 完成要求

每次完成任务前，应报告：

- 修改的文件。
- 相关的 `spec-superflow` artifact 或用户请求来源。
- 执行过的验证命令及结果。
- 未解决的假设、风险或需要用户确认的范围问题。
