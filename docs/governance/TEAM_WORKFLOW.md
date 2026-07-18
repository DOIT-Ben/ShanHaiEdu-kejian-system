# 团队任务、分支与交接流程

本文件定义一个开发任务从提出到关闭的完整生命周期。产品与工程事实不写在这里，分别维护在现行产品、工作流、合同和模块文档中。已证实的协作失败机制及防复发状态见[协作机制复盘与防复发](协作机制复盘与防复发.md)。

## 1. 协作模型

- GitHub Issue是任务、验收、决策和任务状态的唯一事实源。
- GitHub Pull Request是实现变更、测试证据、评审和交接的唯一事实源。
- `CURRENT_STATUS.md`只汇总当前里程碑、活跃任务、阻塞和下一阶段出口。
- Git提交保存实现历史，当前树不保存任务日志或版本副本。

一个任务只有一个当前负责人、一个主分支和一个主PR。需要多人并行时，建立父Issue和可独立验收的子Issue，不共用一条长期分支。

## 2. Issue类型与状态

使用三种Issue模板：

- Task：功能、重构、文档、测试和基础设施工作。
- Bug：可以复现的实现缺陷。
- Decision：会改变产品主线、跨模块合同、核心数据或长期技术方向的决定。

状态标签固定为：

```text
status:ready
status:in-progress
status:blocked
status:review
status:done
```

建议配套标签：

```text
type:feature  type:bug  type:refactor  type:docs  type:decision
area:web      area:api  area:workflow  area:model-gateway
area:asset    area:ppt  area:video     area:infra
priority:p0   priority:p1  priority:p2
```

标签用于检索，不能代替Issue正文。

## 3. Definition of Ready

Issue进入`ready`前必须写清：

1. 用户或系统要获得的结果。
2. 本任务包含和不包含的范围。
3. 可验证的验收标准。
4. 受影响的前端、后端、数据库、合同、工作流和文档。
5. 前置依赖、已知风险和当前阻塞。
6. 需要运行的测试或演示。
7. 所属GitHub Milestone。

缺少以上信息的Issue不能进入开发。任务大到无法在一个PR中独立审核时，必须拆成父子Issue。

## 4. 开始任务

负责人领取Issue后先更新远端引用。主工作区存在用户改动或属于其他任务时，不切换它；直接从最新`origin/main`创建仓库外短工作树：

```bash
git fetch origin --prune
git worktree add -b feat/123-project-assets ../shanhaiedu-worktrees/123-project-assets origin/main
```

分支格式为：

```text
<type>/<issue-number>-<short-kebab-name>
```

允许的类型：`feat`、`fix`、`refactor`、`docs`、`test`、`chore`、`hotfix`。

创建分支当天必须：

- 将Issue状态改为`status:in-progress`。
- 创建Draft PR并关联Issue。
- 在PR中保留验收、风险和测试清单。

普通任务目标周期不超过3个工作日。超过5个工作日仍不可合并时，暂停新增内容，拆分任务或重新确认范围。

## 5. 本地并行工作

一个工作目录只处理一个分支。需要并行时使用仓库外部Git worktree：

```bash
mkdir -p ../shanhaiedu-worktrees
git worktree add ../shanhaiedu-worktrees/123-project-assets feat/123-project-assets
```

禁止在仓库内部创建第二份clone、源码副本、`backup/`、`copy/`或任务临时目录。

创建前必须验证目标绝对路径位于约定的worktree根中；创建后核对分支、HEAD、upstream和工作区。不得在带有其他任务或用户改动的主工作区执行`git switch main`来为任务腾位置。

开始修改前检查：

```bash
git status --short --branch
git log -1 --oneline
```

发现不属于当前任务的改动时停止，不得顺手提交或删除。

## 6. 提交规范

提交使用Conventional Commits：

```text
feat(workflow): add lesson-plan generation node
fix(asset): prevent duplicate project asset save
refactor(gateway): isolate provider adapters
docs(governance): define task handoff protocol
test(ppt): enforce white body background
```

提交应形成可解释的逻辑单元。禁止使用“更新”“继续”“最终版”“修复问题”等无范围信息。

交接前未完成的分支允许`WIP:`提交，PR保持Draft，正文必须列出失败检查和下一动作。最终Squash Merge不会把WIP提交带入`main`历史。

## 7. Pull Request要求

PR正文必须包含：

- `Closes #<issue>`。
- 结果摘要和明确非范围。
- 关键实现决定。
- 前端、后端、数据、合同、工作流和文档影响。
- 精确测试命令与结果。
- 数据迁移和回退说明。
- 界面或真实产物验证。
- 风险、遗留项及其Issue链接。
- 删除的旧代码或旧文档。
- 独立子智能体审查人、审查范围、findings处置、验证命令和残余风险。
- `CURRENT_STATUS.md`新鲜度二选一声明及判断依据；触发状态页更新时，必须在同一PR同步状态页。
- PR规模二选一声明；原始变更超过20个文件、净新增超过800行或包含二进制/未知统计项时选择`pr-size-review-map-required`，列出业务源码、生成物、Schema、迁移和测试的评审导航，并说明为何不能继续拆分。

超过20个业务源码文件或800行净新增非生成代码的PR，必须提供评审导航并说明为何不能拆分。初始化、生成代码、Schema和迁移可以例外，但应与手写业务代码分开列出。

SHA必须由`git rev-parse`或`gh pr view --json baseRefOid,headRefOid`取得，不得手工扩写短SHA。PowerShell中更新多行PR正文或评论时使用UTF-8正文文件、标准输入或结构化API，不把含反引号、美元符号和换行的Markdown拼进插值命令。更新后必须重新读取远端正文，并运行PR声明校验。Draft可使用`subagent-review-pending`；PR正文编辑和转Ready都会重新触发校验，非Draft必须使用`subagent-review-approved`并绑定当前SHA。

## 8. 变更分级

### 模块内部调整

不改变业务语义、数据或外部合同。Issue和PR说明即可，更新相关测试。

### 合同或数据调整

同一PR必须完成：

- OpenAPI或JSON Schema变更。
- 所有当前消费者同步。
- Alembic迁移和兼容窗口。
- 合同测试。
- 回退或前向修复方案。

字段删除、重命名、从可选变必填、语义改变或取值范围收窄均属于破坏性变更。

### 产品或主工作流调整

先建立Decision Issue，记录问题、候选方案、选择理由和影响范围。确认后直接修改现行文档、合同、实现和测试，并在同一PR删除失效口径。

禁止通过补充说明或同时支持两套相反语义绕开决策。

## 9. 数据与内容发布

- 数据库只使用Alembic迁移，采用扩展、回填、切换、清理顺序。
- 内容包、工作流定义、Prompt和Schema发布后不可变；调整时发布新版本。
- 项目固定内容与工作流版本，显式迁移前必须展示差异。
- 紧急安全覆盖必须审计并建立后续正式内容发布Issue。
- 模型供应商密钥和真实用户素材不得进入Issue、PR、日志或仓库。

## 10. 审核与合并

`main`必须启用分支保护。最低要求：

- 禁止直接推送和强推。
- 必需状态检查通过。
- 对话已解决。
- 线性历史。
- 合并后自动删除分支。

仓库的工程批准由独立只读子智能体完成，不要求另一个GitHub账号提交`APPROVED`。主智能体必须指定一个未参与实现的子智能体，启动一次审查engagement并审查完整base-to-head diff。初审发现问题后由同一审查者复核修复和最终diff，不重复启动新的全量审查；只有原审查者不可用或范围发生实质变化时才更换，并在PR说明原因。任何push、rebase或其他HEAD变化都会使原批准失效，必须由同一审查者重新绑定最终base/head。P0/P1未关闭时不得转Ready或合并；P2/P3必须修复，或由主智能体在PR中说明接受理由和残余风险。子智能体与主智能体共享GitHub凭据时，不伪造平台Review；分支保护以必需状态检查、线性历史和对话解决作为机器门禁。

默认使用Squash Merge，PR标题作为主分支提交信息。鉴权、核心数据表、破坏性合同、模型费用策略和发布基础设施仍须在子智能体审查中显式覆盖对应风险边界。

从专用worktree合并时只执行`gh pr merge <PR> --squash`，不附加会切换或删除本地分支的`--delete-branch`。仓库设置负责合并后删除远端分支；本地分支和worktree在main复验后单独清理。合并命令返回后必须重新读取PR状态、merge commit、远端分支和当前worktree分支，不能假定CLI没有改变本地状态。

合并前检查：

- 分支与最新`main`兼容且无冲突。
- 验收标准全部满足。
- 独立子智能体审查报告已绑定当前base/head SHA并留在PR，所有findings已经关闭或显式接受；审查后没有新的HEAD变化。
- 测试、构建、迁移和真实产物验证达到风险要求。
- 文档、合同和实现一致。
- 失效文件已经删除。
- 遗留工作已创建独立Issue，不使用无归属TODO。

## 11. Definition of Done

任务同时满足以下条件才是`done`：

1. 验收标准通过。
2. 必需检查通过并记录证据。
3. 独立子智能体审查通过，PR记录审查范围、findings处置和残余风险。
4. 数据、合同、实现、测试和现行文档一致。
5. PR已Squash Merge。
6. Issue通过`Closes`自动关闭。
7. 远端任务分支已删除。
8. 本地分支和worktree已清理。
9. 任务导致进入新里程碑、可演示能力实质变化、新增或解除阶段阻塞，或下一阶段出口改变时，已在同一PR更新`CURRENT_STATUS.md`；不触发时已在PR明确声明。

合并后的main复验与本地清理：

```bash
# 在任务worktree中
git fetch origin --prune
git switch --detach origin/main
# 运行该任务要求的main复验
git status --short --branch

# 回到主仓或另一个已登记worktree中
git -c core.longpaths=true worktree remove <verified-absolute-worktree-path>
git worktree prune
git branch -D feat/123-project-assets
```

移除worktree前先删除其中可再生的`.venv`、`node_modules`和任务缓存，并再次确认工作区干净、绝对路径位于约定根目录。`branch -D`只允许在PR已`MERGED`、远端分支已删除、main复验通过且worktree已移除后用于精确任务分支；Squash Merge后不能用祖先关系代替这些证据。若Git已注销worktree但物理目录因Windows长路径或重解析点残留，先证明目录无`.git`、不含外部指向的重解析点且只含可再生内容，再使用支持长路径的单一路径清理方式；禁止对父目录递归删除或连续试用多种未核验删除命令。

## 12. 标准交接

暂停、换人或结束会话前，把以下内容写入Issue或Draft PR：

```text
目标：
当前状态：
已经完成：
尚未完成：
下一步唯一动作：
相关分支：
最新提交：
对应PR：
修改的主要文件：
已经运行的测试：
当前失败或阻塞：
本次确认的决定：
需要特别避免的事项：
```

交接前必须推送安全检查点。只有本地未提交文件、聊天摘要或口头描述不构成交接。

## 13. 放弃与关闭

放弃任务时：

1. 在PR说明原因和可复用结论。
2. 关闭PR。
3. 将Issue恢复为`ready`或标记取消。
4. 删除远端分支。
5. 删除本地分支和worktree。

不得保留“以后可能有用”的孤立分支。
