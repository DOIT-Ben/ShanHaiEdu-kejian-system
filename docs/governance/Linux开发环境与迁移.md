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

### 3.1 宿主身份与Git元数据恢复

宿主机上的Git、`fsck`、`fetch`、`status`、`worktree`、`compose.sh`、uv和测试命令统一由`shanhai-dev`执行；root只承担已明确授权的主机运维，不运行Git，不启动开发Compose，不执行项目测试。Issue worktree只在`/srv/shanhaiedu/worktrees/`下创建，主仓不为任务切换分支。容器只读挂载Git元数据，workspace固定`GIT_OPTIONAL_LOCKS=0`，验证入口还会把当前index复制到系统临时目录后通过`GIT_INDEX_FILE`读取，避免生成/校验命令刷新宿主index；任何需要写ref、object、reflog或worktree登记的操作都回到宿主机并使用`shanhai-dev`。

双角色边界固定：`shanhai-dev`负责所有Git操作和下面的无修改可访问性检测；受控管理员仅能以root-only身份执行精确备份、备份的可读性/完整性验证、逐路径权限修复和事故恢复。管理员不得用root Git绕过检测，也不得代替`shanhai-dev`判断工作树或对象库是否正常。

root的GitHub CLI登录态只允许通过显式仓库和API端点读取或更新GitHub Issue、Pull Request等远端元数据，不得据此执行本地Git、改变本地文件属主，或把Token、Cookie和认证文件复制给`shanhai-dev`。需要同时操作GitHub与本地仓库时，将两步分开：root使用`gh api`处理远端API，`shanhai-dev`使用`git`处理本地提交、fetch、worktree和push。

每次接手、fetch失败或Git报告对象、ref、reflog、worktree权限异常时，先执行无修改检测。下面所有Git和文件可访问性检查都以`shanhai-dev`运行；任何输出或非零退出都视为漂移，不用root重跑Git来绕过错误。`find -P`禁止跟随符号链接：对任何链接先用`lstat`和`readlink`记录，发现链接、断链或解析越界即fail closed并升级，不把链接当作普通文件修复：

```bash
set -eu -o pipefail
repo=/srv/shanhaiedu/repository
git_common_dir=$(sudo -u shanhai-dev -- git -C "$repo" rev-parse --path-format=absolute --git-common-dir) || exit 1
worktree_root=/srv/shanhaiedu/worktrees
repo_git_entry="$repo/.git"

# 主仓必须使用本地普通 .git 目录；不能接受 symlink、gitdir 指针文件或
# 解析到仓库外的公共目录。rev-parse 的结果必须与固定 .git 目录完全相等。
repo_git_kind=$(sudo -u shanhai-dev -- stat --format='%F' -- "$repo_git_entry") || exit 1
case "$repo_git_kind" in
  directory) ;;
  symbolic\ link)
    sudo -u shanhai-dev -- readlink -- "$repo_git_entry" >&2 || exit 1
    printf 'repository .git must not be a symbolic link: %s\n' "$repo_git_entry" >&2
    exit 1
    ;;
  *)
    printf 'repository .git must be a directory, got %s: %s\n' "$repo_git_kind" "$repo_git_entry" >&2
    exit 1
    ;;
esac
expected_common_dir=$(sudo -u shanhai-dev -- realpath -e -- "$repo_git_entry") || exit 1
resolved_common_dir=$(sudo -u shanhai-dev -- realpath -e -- "$git_common_dir") || exit 1
if [ "$resolved_common_dir" != "$expected_common_dir" ]; then
  printf 'rev-parse common Git directory does not match repository .git: %s != %s\n' \
    "$resolved_common_dir" "$expected_common_dir" >&2
  exit 1
fi
git_common_dir=$expected_common_dir

# 仅由 shanhai-dev 执行；公共 Git 目录和每个登记 worktree 内的目录必须
# 由该账号拥有且可读、可写、可搜索，普通文件必须由该账号拥有且可读。
check_tree() {
  root=$1
  if ! directories=$(sudo -u shanhai-dev -- find -P "$root" -xdev -type d \
    \( ! -user shanhai-dev -o ! -readable -o ! -writable -o ! -executable \) -print 2>&1); then
    printf 'directory permission scan failed: %s\n' "$root" >&2
    return 1
  fi
  if ! files=$(sudo -u shanhai-dev -- find -P "$root" -xdev -type f \
    \( ! -user shanhai-dev -o ! -readable \) -print 2>&1); then
    printf 'file permission scan failed: %s\n' "$root" >&2
    return 1
  fi
  if ! links=$(sudo -u shanhai-dev -- find -P "$root" -xdev -type l -print 2>&1); then
    printf 'symlink scan failed: %s\n' "$root" >&2
    return 1
  fi
  if ! specials=$(sudo -u shanhai-dev -- find -P "$root" -xdev \
    ! \( -type d -o -type f -o -type l \) -print 2>&1); then
    printf 'special-file scan failed: %s\n' "$root" >&2
    return 1
  fi
  if [ -n "$directories" ] || [ -n "$files" ]; then
    printf 'Git path ownership/readability/rwx drift under %s:\n%s\n%s\n' \
      "$root" "$directories" "$files" >&2
    return 1
  fi
  if [ -n "$links" ]; then
    while IFS= read -r link; do
      # stat 不加 -L 时等价于 lstat；再用 readlink 记录目标，任何链接都 fail closed。
      sudo -u shanhai-dev -- stat --format='%F %U %a %n' -- "$link" >&2 || return 1
      sudo -u shanhai-dev -- readlink -- "$link" >&2 || return 1
    done <<< "$links"
    return 1
  fi
  if [ -n "$specials" ]; then
    while IFS= read -r special; do
      # FIFO、socket、device 或未知类型全部拒绝；stat 只读取元数据，不打开对象。
      sudo -u shanhai-dev -- stat --format='%F %U %a %n' -- "$special" >&2 || return 1
    done <<< "$specials"
    printf 'special Git entry is forbidden: %s\n' "$specials" >&2
    return 1
  fi
}

# 对系统级父目录只核对 shanhai-dev 的读取和搜索（execute）权限；
# 例如 /srv 或 /srv/shanhaiedu 不要求归该账号所有。
check_search_parents() {
  path=$1
  while [ "$path" != "/" ]; do
    if ! parent_errors=$(sudo -u shanhai-dev -- find -P "$path" -maxdepth 0 \
      \( ! -readable -o ! -executable \) -print 2>&1); then
      printf 'parent directory scan failed: %s\n' "$path" >&2
      return 1
    fi
    if [ -n "$parent_errors" ]; then
      printf 'Parent directory is not readable/searchable: %s\n' "$parent_errors" >&2
      return 1
    fi
    next=$(dirname -- "$path")
    [ "$next" = "$path" ] && break
    path=$next
  done
}

check_writable_root() {
  path=$1
  kind=$(sudo -u shanhai-dev -- stat --format='%F' -- "$path") || return 1
  case "$kind" in
    directory) ;;
    symbolic\ link)
      sudo -u shanhai-dev -- readlink -- "$path" >&2 || return 1
      printf 'writable root must not be a symbolic link: %s\n' "$path" >&2
      return 1
      ;;
    *)
      printf 'writable root is not a directory: %s (%s)\n' "$path" "$kind" >&2
      return 1
      ;;
  esac
  resolved=$(sudo -u shanhai-dev -- realpath -e -- "$path") || return 1
  if [ "$resolved" != "$path" ]; then
    printf 'writable root resolves outside its declared path: %s -> %s\n' \
      "$path" "$resolved" >&2
    return 1
  fi
  if ! writable_errors=$(sudo -u shanhai-dev -- find -P "$path" -maxdepth 0 -type d \
    \( ! -user shanhai-dev -o ! -readable -o ! -writable -o ! -executable \) -print 2>&1); then
    printf 'writable root scan failed: %s\n' "$path" >&2
    return 1
  fi
  if [ -n "$writable_errors" ]; then
    printf 'Writable Git parent is not owned/readable/writable/searchable by shanhai-dev: %s\n' \
      "$writable_errors" >&2
    return 1
  fi
}

assert_common_path() {
  target=$1
  case "$target" in
    "$git_common_dir"|"$git_common_dir"/*) ;;
    *)
      printf 'gitdir target escapes common Git directory: %s\n' "$target" >&2
      return 1
      ;;
  esac
  check_search_parents "$target"
}

check_git_pointer() {
  worktree=$1
  if ! git_pointer_paths=$(sudo -u shanhai-dev -- find -P "$worktree" -maxdepth 1 \
    -name .git -print 2>&1); then
    printf '.git pointer scan failed: %s\n' "$worktree" >&2
    return 1
  fi
  if [ -z "$git_pointer_paths" ]; then
    printf 'missing .git entry: %s\n' "$worktree" >&2
    return 1
  fi
  pointer_count=0
  while IFS= read -r git_pointer; do
    pointer_count=$((pointer_count + 1))
    # stat 不加 -L 时读取链接本身（lstat 语义），不可把符号链接当作普通对象。
    kind=$(sudo -u shanhai-dev -- stat --format='%F' -- "$git_pointer") || return 1
    case "$kind" in
      directory)
        target=$(sudo -u shanhai-dev -- realpath -e -- "$git_pointer") || return 1
        assert_common_path "$target"
        ;;
      regular\ file)
        pointer_line=$(sudo -u shanhai-dev -- sed -n '1p' -- "$git_pointer") || return 1
        case "$pointer_line" in
          "gitdir: "*)
            raw_target=${pointer_line#gitdir: }
            case "$raw_target" in
              /*) candidate=$raw_target ;;
              *) candidate=$worktree/$raw_target ;;
            esac
            target=$(sudo -u shanhai-dev -- realpath -e -- "$candidate") || return 1
            assert_common_path "$target"
            ;;
          *)
            printf 'invalid gitdir pointer: %s\n' "$git_pointer" >&2
            return 1
            ;;
        esac
        ;;
      symbolic\ link)
        sudo -u shanhai-dev -- readlink -- "$git_pointer" >&2 || return 1
        printf 'symbolic .git entry is forbidden: %s\n' "$git_pointer" >&2
        return 1
        ;;
      *)
        printf 'unsupported .git entry type %s: %s\n' "$kind" "$git_pointer" >&2
        return 1
        ;;
    esac
  done <<< "$git_pointer_paths"
  [ "$pointer_count" -eq 1 ] || {
    printf 'expected one .git entry, got %s: %s\n' "$pointer_count" "$worktree" >&2
    return 1
  }
}

check_tree "$git_common_dir"
registered_worktrees=$(sudo -u shanhai-dev -- git -C "$repo" worktree list --porcelain \
  | sed -n 's/^worktree //p')
[ -n "$registered_worktrees" ] || {
  printf 'no registered worktree was returned\n' >&2
  exit 1
}
while IFS= read -r worktree; do
  case "$worktree" in
    "$repo"|"$worktree_root"/*) ;;
    *)
      printf 'registered worktree escapes allowed roots: %s\n' "$worktree" >&2
      exit 1
      ;;
  esac
  check_tree "$worktree"
  check_writable_root "$worktree"
  check_git_pointer "$worktree"
  check_search_parents "$worktree"
done <<< "$registered_worktrees"

# 新建 worktree 需要写入 worktree 根；Git 还需要写入公共目录及其
# worktrees 登记目录。它们必须由 shanhai-dev 拥有并具备 rwx；其系统级
# 祖先目录只需可读/可搜索。
check_writable_root "$repo"
check_writable_root "$worktree_root"
check_writable_root "$git_common_dir"
if [ -d "$git_common_dir/worktrees" ]; then
  check_writable_root "$git_common_dir/worktrees"
fi
check_search_parents "$repo"
check_search_parents "$worktree_root"
check_search_parents "$git_common_dir"

# 任一 find 非零、异常输出、lstat/readlink 异常、父目录不可搜索或 .git 指针越界，
# 都必须停止；不得用 root 重跑、静默过滤或只看单个成功命令。
```

上面的包装片段可以由受控管理员启动，但每个`git`、`find`、`stat`、`readlink`和`realpath`子进程都必须实际以`shanhai-dev`身份运行；`sudo -u shanhai-dev`只是显式固定身份，不是授权root直接操作Git。`shanhai-dev`自行复验时可在其受控Shell中去掉该前缀，结果和门禁不变。

正式复验使用以下命令：

```bash
sudo -u shanhai-dev -- git -C "$repo" fsck --full
sudo -u shanhai-dev -- git -C "$repo" fetch origin --prune
sudo -u shanhai-dev -- git -C "$repo" status --short --branch
sudo -u shanhai-dev -- git -C "$repo" worktree list --porcelain
```

发现漂移后按以下顺序恢复，不跳过备份：

1. 由受控管理员以root-only身份把Git公共元数据及其UID、GID、mode、ACL和扩展属性清单备份到`/srv/shanhaiedu/backups/<timestamp>/`。备份目录保持`root:root`、`0700`，归档保持`root:root`、`0600`，不为`shanhai-dev`放宽读取权限；备份不包含工作区密钥、运行数据或用户素材。管理员必须列举归档内容并记录SHA-256，且确认`getfacl`/`getfattr`等ACL/xattr工具可用并保存证据；工具缺失、证据缺失、归档不可读或摘要不匹配都fail closed，不能进入修复。
2. 管理员核对异常清单中的每个绝对路径都位于已解析的Git公共目录内，并用`lstat`/`readlink`确认不是符号链接或越界指针。只有在备份证据完整、路径通过重新解析且目标为普通文件/目录时，才可对单个精确路径逐项执行`chown -- shanhai-dev:shanhai-dev <exact-path>`；仅在原mode本身异常且已记录时逐项修正mode。发现符号链接必须停止并升级；若有单独批准的链接修复，只能在再次核验后使用`chown -h --from=...`，不得默认解引用。禁止`chown -R`、`chmod -R`、对仓库父目录批量改权或删除/重建`.git`。
3. 再次运行无修改检测，要求非`shanhai-dev`属主和不可读条目均为零；随后依次运行`fsck --full`、`fetch origin --prune`、`status --short --branch`和`worktree list --porcelain`，由真实Git操作验证所需写权限。逐个核对refs、当前分支、dirty文件和已登记worktree，不以单个命令通过代替整套复验，也不通过reset清理用户改动。
4. 不得把tar归档直接覆盖解压到活动`.git`或公共Git目录。若需要恢复，受控管理员先解包到隔离临时目录，重新核对路径、UID/GID、mode、ACL和xattr，再依据批准的清单对精确对象逐项恢复；若发现对象、ref、reflog或worktree内容损坏，停止权限操作并保留现场，由受控管理员从已验证归档制定单独恢复方案。
5. 若只变更了属主或mode，回退时按备份清单对同一批精确路径逐项恢复原UID、GID和mode；回退仍由管理员执行，恢复后的Git复验仍由`shanhai-dev`执行。

备份不可读、归档摘要不匹配、ACL/xattr工具或证据缺失、异常路径越出Git公共目录、发现符号链接、需要改变Git内容、复验仍报对象或ref错误，或第二次精确修复后仍出现新漂移时，必须升级为独立基础设施事故。此时禁止继续等价重试、全仓改权、重新clone覆盖现场、把tar覆盖解压到活动`.git`或删除对象；保留备份、权限清单和脱敏命令结果，并在Issue中记录下一步最小动作。

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
bash infra/dev/compose.sh exec workspace uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
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
