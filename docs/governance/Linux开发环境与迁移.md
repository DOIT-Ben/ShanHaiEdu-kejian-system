# Linux开发环境与迁移

所有者：项目工程负责人
受众：后端、前端、基础设施、外包和编码智能体
权威路径：`docs/governance/Linux开发环境与迁移.md`
替换规则：开发拓扑改变时原地修改；退回宿主机原生开发时在同一PR删除本文和`infra/dev/`

## 1. 决定

ShanHaiEdu使用阿里云Linux开发生产级代码，正式生产部署在后续独立Issue中建设。主要开发方式固定为：

```text
开发者或Codex
→ SSH进入Linux开发主机
→ Git仓库外短worktree
→ Docker Compose workspace容器
→ PostgreSQL、Redis、MinIO依赖容器
```

Windows只保留应急回退，不再作为日常开发入口。Linux宿主机只安装Git、Docker Engine、Docker Compose和受控SSH/Codex入口。Python、Node、uv、pnpm、FFmpeg、LibreOffice和项目依赖只安装在版本固定的workspace镜像或持久依赖卷中。

不采用服务器原生安装项目工具链，因为它会重新形成环境漂移；不只依赖编辑器专有Dev Container入口，因为命令行、Codex和CI必须使用同一容器合同。

## 2. 固定基线

- Linux：Ubuntu 22.04 LTS，x86_64。
- Python：3.12.12。
- Node.js：22.22.0。
- uv：0.10.6。
- pnpm：10.30.2。
- PostgreSQL：16.14。
- Redis：7.4.9。
- Docker Compose：2.40以上。
- 媒体工具：Debian Bookworm仓库中的FFmpeg、LibreOffice Impress和Poppler。

workspace镜像使用`shanhaiedu-dev-workspace:2026.07-v2`版本标签，基础层使用tag加OCI digest固定；固定版本的pnpm及其Corepack缓存直接进入镜像，运行容器不再下载工具链。只有环境合同变化时，才由独立Issue修改Dockerfile、镜像标签、锁文件和Linux验证证据；日常worktree复用现有镜像，不在服务器上临时升级或重复构建。

## 3. 主机容量与目录

推荐容量为8 vCPU、16 GiB内存和100 GiB级文件系统；这里的100 GiB指文件系统总容量，不要求始终有100 GiB空闲。开始试运行前至少保留30 GiB空闲空间；低于该门禁时停止构建，不执行未经批准的镜像、缓存或项目目录清理。

2026-07-19只读复核确认，目标阿里云ECS的`/dev/vda3`已经是99.8 GiB ext4根分区，根文件系统当前约66 GiB空闲。该主机容量条件已满足，不再以根分区扩容或新增数据盘作为试运行前置条件。任何目标主机在根文件系统或独立数据盘空闲不足30 GiB时，仍不得构建workspace镜像或启动ShanHaiEdu开发栈；不得通过清理现有容器、镜像、卷或其他项目绕过门禁。

开发环境优先使用独立ECS，避免与已有容器共享Docker daemon、root权限边界和磁盘故障域。如果只能暂时使用现有ECS，必须由`shanhai-dev`运行rootless Docker；不得把加入共享rootful Docker组或仅使用不同Compose项目名当作安全隔离。

`compose.sh`默认拒绝未声明的Docker daemon。`rootless`模式必须从Docker安全选项中检测到rootless；此时workspace以容器UID/GID 0运行，该身份只映射为宿主普通用户`shanhai-dev`，用于保持源码bind mount可写，不具备宿主root权限。`dedicated-ecs`模式要求宿主`shanhai-dev`固定为UID/GID 1000:1000，并要求基础设施在`/etc/shanhaiedu/dedicated-development-host`写入唯一内容`shanhaiedu-dedicated-development-host-v1`；该标记只允许在确认主机不承载其他项目后由主机配置流程创建。

Ubuntu 22.04共享ECS的rootless daemon可能没有可委派的CPU CFS控制器。包装脚本在`rootless`模式下将Compose CPU配额设为`0`，避免把不受内核支持的`NanoCPUs`发送给daemon；内存、进程数和worktree隔离仍保留。`dedicated-ecs`模式继续使用各服务的固定CPU配额。共享ECS运行rootless任务时仍受最多三个后端主任务和人工资源观察约束，不得用切换全机cgroup模式或重启宿主机处理该差异。

正式目录使用非root账号`shanhai-dev`：

```text
/srv/shanhaiedu/repository/     主仓库
/srv/shanhaiedu/worktrees/      Issue短worktree
/srv/shanhaiedu/runtime/        非Git运行数据
/srv/shanhaiedu/backups/        迁移与回退清单
```

源码和worktree归`shanhai-dev`所有。该账号不得加入现有共享rootful Docker组，不读取其他项目的密钥目录。现有`/root/Codex-Projects`不作为正式ShanHaiEdu运行路径。

## 4. 启动与统一命令

Linux Shell是唯一日常开发命令入口，不再维护容易漂移的PowerShell等价命令；Windows应急只从已推送分支恢复工作树。先在宿主Shell显式选择已经满足的隔离模式；未设置、rootless检测失败、独立ECS标记缺失或容量不足时，脚本会在调用Compose前停止：

```bash
export SHANHAI_DOCKER_ISOLATION_MODE=rootless
# 已配置受控标记的独立ECS使用 dedicated-ecs。
```

首次建立环境或环境合同变化时显式构建版本化镜像：

```bash
bash infra/dev/compose.sh build workspace
```

日常worktree只启动，不默认使用`--build`：

```bash
bash infra/dev/compose.sh up -d
bash infra/dev/compose.sh exec workspace bash infra/dev/bootstrap.sh
bash infra/dev/compose.sh exec workspace bash infra/dev/verify.sh
```

进入容器或启动API：

```bash
bash infra/dev/compose.sh exec workspace bash
bash infra/dev/compose.sh exec workspace uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

停止容器但保留开发数据卷：

```bash
bash infra/dev/compose.sh down
```

`compose.sh`从当前Git工作树解析公共Git目录和worktree管理目录，只读挂载Git元数据，并按worktree目录派生唯一Compose项目名和一组稳定宿主端口。容器内可以运行依赖`git ls-files`的验证，但Commit、Push和worktree管理仍在宿主机执行。禁止在日常停止时使用`down -v`。只有确认卷内全部是可再生开发数据并获得清理授权后才能删除精确命名卷。

## 5. Worktree与并发

每个Issue仍使用仓库外短worktree。`compose.sh`优先从worktree名称中的Issue编号派生端口偏移，没有编号时使用目录名校验和；因此PostgreSQL、Redis、MinIO和API默认获得不同宿主端口。显式端口覆盖仍可用，但覆盖者必须自行保证不冲突。Compose项目名负责隔离PostgreSQL、Redis、MinIO、`.venv`和`node_modules`。

所有worktree共享只读的版本化workspace镜像，以及固定命名的`shanhaiedu-dev-uv-cache-v1`和`shanhaiedu-dev-pnpm-store-v1`下载缓存卷，避免重复下载和磁盘膨胀。下载缓存不是业务事实源；`.venv`、`node_modules`、数据库、Redis和MinIO业务数据必须保持worktree级隔离。

同一数据库迁移、合同或跨模块事务仍不得竞争写入。Docker隔离不能替代Issue依赖、三任务上限和独立审查规则。

## 6. 数据、缓存和密钥

- Git只迁移源码、锁文件、迁移和可重复脚本。
- `.venv`、`node_modules`和开发业务数据使用worktree级Compose命名卷，不复制Windows目录。
- uv缓存、pnpm store和版本化workspace镜像跨worktree共享；缓存卷只保存可再生下载，不得写入业务数据、密钥或项目产物。
- 上传、模型响应、媒体中间件和导出文件放在`runtime/`或对象存储，不进入仓库。
- 普通CI和开发验证使用确定性Fake；真实Provider密钥只从受控宿主环境或Docker Secret注入。
- `.env`只允许非敏感开发配置。真实Key不得写入`.env`、Compose YAML、镜像层、Issue、PR或Shell历史。
- 生产数据库、对象存储和现有网关数据不进入本迁移，不挂载到开发Compose项目。

## 7. 迁移阶段

### 非生产试验

1. 核对主机容量、Docker版本、现有服务和端口，并完成独立ECS受控标记或rootless Docker检测。
2. 在独立目录克隆Git仓库，不复制Windows工作树或依赖目录。
3. 构建workspace镜像并运行`bootstrap.sh`。
4. 运行`verify.sh`，记录Linux符号链接、长路径、迁移、合同和集成结果。
5. 普通`down`并验证现有服务器容器未变化。

### 双轨期

Linux完成一次完整环境验证，并完成一个真实Issue的开发、审查、合并和清理后，即切换为主要开发入口，Windows降为应急回退。双轨期间GitHub分支和PR是唯一代码交接，不在两台机器之间复制未提交工作树。

### 正式切换

同时满足以下门禁后，主要开发入口切到Linux：

- Linux完整环境验证通过。
- 至少一个真实Issue已在Linux完成开发、审查、合并和清理闭环。
- 重启后workspace和依赖恢复演练通过。
- 备份清单和Git恢复演练通过。
- 密钥注入不依赖仓库文件。
- 工作树与命名卷清理流程通过。
- Windows不再承担唯一未提交代码、数据库或素材。

## 8. 回退

试运行失败时停止Linux Compose项目并保留卷，代码从已推送分支在Windows重新建立worktree。生产服务和数据未参与迁移，因此不执行数据库回滚或流量切换。

磁盘扩容、分区调整、Docker根目录迁移、用户权限变更和生产数据移动属于独立高风险操作，必须先备份并获得明确授权。不得为了通过试运行直接清理服务器现有镜像、容器、卷或其他项目。
