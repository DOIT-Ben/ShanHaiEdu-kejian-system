# 生产公网 IP 发布

责任人：Issue #244 生产发布负责人。

读者：执行、审查或回退山海教育生产发布的运维与开发人员。

规范路径：`infra/prod/README.md`。生产拓扑变化时原位更新，不建立日期副本。

## 边界

本目录把生产运行与共享 ECS 上的开发环境隔离：

- 根目录固定为 `/opt/shanhaiedu-production`，每个 exact Git SHA 位于 `releases/<sha>`。
- Compose 项目固定为 `shanhaiedu-production`；PostgreSQL、Redis、MinIO 使用独立命名卷。所有服务共享无默认路由的 `production` internal 网络；只有不挂载 Secret 的 Web/Caddy 额外挂载关闭 IP masquerade 的 `loopback` bridge，并在 internal 网络内按固定路径反代 API 与 MinIO。只有 Worker 额外挂载不发布端口、关闭容器互访的 `provider-egress` bridge，获得文本 Provider 所需的主动出网能力。该通用 NAT bridge 不提供目的地址白名单。
- 只有 Web/Caddy `127.0.0.1:18080` 暴露给宿主机 Nginx；API、Worker、PostgreSQL、Redis 和 MinIO 不发布宿主端口。宿主 Nginx 覆盖客户端提供的 `X-Forwarded-For`，Caddy 仅按严格私网代理链保留真实客户端 IP。
- Secret 只保存在 `shared/secrets` 的 root-owned `0600` 文件中，并通过 Compose secret 挂载。文本 Provider 密钥固定写入 `text_provider_api_key`，只挂载给 Worker；非密钥路由字段写入 `shared/production.env`。
- API、Web、PostgreSQL、Redis 和 MinIO 禁止主动访问公网。只有 Worker 获得通用主动出网；目的地址未由网络层限制，而由 root-owned 生产配置和 Model Gateway 路由约束为受控文本 Provider。该边界仍存在 Worker 被攻陷后可访问其他可路由地址的残余风险；不得借此接入图片、视频或 TTS Provider。

共享 ECS 仍有资源争用和共同故障风险。该风险由董事长在 Issue #244 明确接受，不得把本拓扑描述为物理隔离。

## 目录

```text
/opt/shanhaiedu-production/
  current -> releases/<sha>
  previous-release -> releases/<previous-sha>
  releases/<sha>/
  shared/production.env
  shared/secrets/
  shared/nginx-backup/
  shared/certbot/
  backups/
```

## 首次发布

1. 从已审查并合并的 exact `origin/main` 生成 Git bundle，在服务器由该 bundle 建立 detached、干净且保留 Git object 校验能力的 `releases/<sha>` checkout，并写入只含 SHA 的 `RELEASE_SHA`。`release.sh` 会拒绝仅靠目录名或手写 manifest 冒充 exact SHA 的目录。
2. 从 `env.example` 创建 `shared/production.env`，写入公网 IP、exact SHA 和固定 Principal ID，权限设为 `0600`。
   文本 Provider 的名称、HTTPS base URL、模型和超时写入同一文件；Secret 环境变量名由生产 Compose 固定，真实密钥单独写入 `shared/secrets/text_provider_api_key`。该 Secret 必须预先存在、由 root 持有、权限为 `0600`、单硬链接且仅含一行非空值；`release.sh` 不生成、不覆盖也不输出它，任一条件不满足会在生产数据写入前停止。
   `SHANHAI_DEBIAN_MIRROR` 只控制 API 镜像构建期的 Debian 下载源，默认使用 Debian 官方 HTTPS 源；受控生产环境可显式覆盖为公开、无凭据、无查询参数或片段、且以 `/debian` 结尾的 HTTPS 镜像。公开镜像 URL 会写入镜像的 APT sources，禁止在该参数中放入密钥或私有 URL。
   `SHANHAI_IMAGE_SOURCE` 默认为 `build`。共享主机无法安全承担镜像构建时，可显式设为 `preloaded`。该模式要求先在 exact checkout 构建 API/Web 镜像，记录导出前不可变 image ID，执行 `docker save` 后记录归档 SHA-256，传输前后核对归档 SHA-256，执行 `docker load` 后再次核对 image ID 与 OCI `org.opencontainers.image.revision` 标签。

   将这四项事实写入 `$SHANHAI_PRODUCTION_ROOT/shared/preloaded-images/<sha>.env`，文件必须由 root 持有、权限为 `0600`，且不得是符号链接：

   ```dotenv
   SHANHAI_RELEASE_SHA=<exact-40-character-sha>
   SHANHAI_PRELOADED_API_IMAGE_ID=sha256:<64-hex>
   SHANHAI_PRELOADED_WEB_IMAGE_ID=sha256:<64-hex>
   SHANHAI_PRELOADED_ARCHIVE_SHA256=<64-hex>
   ```

   `release.sh` 在创建 Secret、备份目录或启动任何生产服务之前验证模式、清单权限、清单字段、当前本地 image ID 和 OCI revision。任一项缺失或不匹配都会停止，且不得靠重打标签绕过 exact 构建来源绑定。
3. 执行：

```bash
sudo /opt/shanhaiedu-production/releases/<sha>/infra/prod/release.sh <sha>
sudo /opt/shanhaiedu-production/releases/<sha>/infra/prod/configure-host.sh
sudo /opt/shanhaiedu-production/current/infra/prod/verify.sh --public
```

`release.sh` 会生成缺失的随机 Secret，但不会覆盖现有 Secret；随后构建 exact SHA 镜像，并在启动 PostgreSQL、Redis 或 MinIO 前通过候选 Worker 的真实 entrypoint 构造 `Settings` 与文本 Model Gateway。该预检只验证完整运行配置和 Secret 注入，不请求 Provider；失败会在数据库或对象存储写入前停止。通过后才启动独立依赖、执行 Alembic、显式创建对象存储桶、发布黄金内容、初始化 access-code 教师、生成 PostgreSQL 与 MinIO 备份并执行独立恢复校验，最后切换 `current`。固定端口服务替换后的任一步失败都会尝试恢复上一应用版本；首次发布失败则停止新应用入口并保留既有 Nginx 站点。

`configure-host.sh` 会按 `SHANHAI_NGINX_SITE_DIR` 和 `SHANHAI_LEGACY_NGINX_SITE` 备份并暂时替换既有公网 IP QA 站点。若环境明确提供 `SHANHAI_TLS_CERTIFICATE` 与 `SHANHAI_TLS_PRIVATE_KEY`，复用主机现有且由独立 timer 续期的 IP 证书；否则才在独立 venv 申请 Let's Encrypt 短期 IP 证书。任何步骤失败会自动恢复旧 Nginx 入口。现有域名站点不在修改范围。

## 验证

`verify.sh` 检查：

- API 的 exact release SHA、liveness 和 readiness；
- Web、PostgreSQL、Redis、MinIO 和 Worker；
- Worker 能从专属 Compose Secret 构造现有真实文本网关路由；该检查不发起 Provider 请求；
- 最近日志中不得出现 Secret 标识；
- Caddy 运行时日志删除请求 URI，Compose 与宿主 Nginx 日志均不得出现 presigned URL 凭据，MinIO 浏览器入口显式关闭 access log；
- 公网 HTTPS 证书必须验证该 IP，公网健康和首页必须可访问。

`configure-host.sh` 会安装五分钟一次的 `shanhaiedu-healthcheck.timer`。健康、证书剩余期限或公网入口失败会使 unit 进入 failed，并通过 `shanhaiedu-health-alert@.service` 写入固定格式的脱敏高优先级日志；运维入口为 `systemctl status`、`journalctl -u shanhaiedu-healthcheck.service` 和 Docker Compose 服务状态。

`release.sh` 与 `rollback.sh` 通过 root-owned `0600` 的 `shared/operations.lock` 持有独占锁；`monitor.sh` 使用同一文件的共享非阻塞锁。锁初始化会拒绝符号链接、非普通文件和多硬链接，并原位保留已存在的锁 inode。systemd healthcheck 也会在解析 `current` 下的监控脚本前获取共享非阻塞锁，使回退到不含此协调逻辑的旧应用版本时仍保持发布互斥。已经开始的监控会在换容器前自然完成，发布或回退进行中触发的定时监控会成功跳过，避免把受控容器替换误报为应用故障。

同一独占锁还保护 `current`、`previous-release` 与 `shared/production.env` 的 exact SHA 切换。发布和回退只接受 root-owned `0600`、单硬链接且仅含一个 `SHANHAI_RELEASE_SHA` 条目的环境文件，并通过同目录原子替换持久更新该字段；环境 SHA 与切换前 `current` 不一致时会在替换应用前停止。切换后的任一步失败会恢复原链接、原环境 SHA 和原应用版本。

真实业务 Playwright 必须从外部客户端运行，使用受控 access code 完成登录、项目创建、教材上传、异步生成、刷新恢复和登出负测。只有 Issue 明确批准的生产验收调用受控真实文本 Provider；普通验证和 CI 不调用真实 Provider。

## 回退

应用错误但数据完整时执行：

```bash
sudo /opt/shanhaiedu-production/current/infra/prod/rollback.sh
```

回退只重启上一版 API、Worker 和 Web 镜像，并在同一独占锁内原子同步 `production.env` 的 exact SHA；不降级数据库、不删除对象和业务事实。回退过程失败时会尝试恢复原应用、链接和环境 SHA。数据完整性或安全问题应停止入口并执行前向修复；不得盲目恢复旧数据库覆盖已确认写入。

首次 Nginx 切换失败由 `configure-host.sh` 的错误 trap 自动恢复。手工恢复时读取 `shared/nginx-backup/latest`，核对 `legacy-site-path` 后恢复原站点文件，并先运行 `nginx -t`。
