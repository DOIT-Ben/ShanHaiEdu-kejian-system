# 生产公网 IP 发布

责任人：Issue #244 生产发布负责人。

读者：执行、审查或回退山海教育生产发布的运维与开发人员。

规范路径：`infra/prod/README.md`。生产拓扑变化时原位更新，不建立日期副本。

## 边界

本目录把生产运行与共享 ECS 上的开发环境隔离：

- 根目录固定为 `/opt/shanhaiedu-production`，每个 exact Git SHA 位于 `releases/<sha>`。
- Compose 项目固定为 `shanhaiedu-production`；PostgreSQL、Redis、MinIO 使用独立命名卷和独立 Docker 网络，宿主暴露端口均绑定回环地址。
- 只有 API `127.0.0.1:18000`、Web `127.0.0.1:18080` 和 MinIO `127.0.0.1:19000` 暴露给宿主机 Nginx。
- Secret 只保存在 `shared/secrets` 的 root-owned `0600` 文件中，并通过 Compose secret 挂载。
- 首次发布不注入 Provider 配置，生产 Docker 网络禁止容器主动访问公网。

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

1. 从已审查并合并的 exact `origin/main` 生成归档，将内容上传到 `releases/<sha>`，并写入只含 SHA 的 `RELEASE_SHA`。
2. 从 `env.example` 创建 `shared/production.env`，写入公网 IP、exact SHA 和固定 Principal ID，权限设为 `0600`。
3. 执行：

```bash
sudo /opt/shanhaiedu-production/releases/<sha>/infra/prod/release.sh <sha>
sudo /opt/shanhaiedu-production/releases/<sha>/infra/prod/configure-host.sh
sudo /opt/shanhaiedu-production/current/infra/prod/verify.sh --public
```

`release.sh` 会生成缺失的随机 Secret，但不会覆盖现有 Secret；随后构建 exact SHA 镜像、启动独立依赖、执行 Alembic、显式创建对象存储桶、发布黄金内容、初始化 access-code 教师、生成备份并在一次性恢复库校验，最后才切换 `current`。

`configure-host.sh` 会先备份并暂时替换既有公网 IP QA 站点，再申请 Let's Encrypt 短期 IP 证书。任何步骤失败会自动恢复旧 Nginx 入口。现有域名站点不在修改范围。

## 验证

`verify.sh` 检查：

- API 的 exact release SHA、liveness 和 readiness；
- Web、PostgreSQL、Redis、MinIO 和 Worker；
- 最近日志中不得出现 Secret 标识；
- 公网 HTTPS 证书必须验证该 IP，公网健康和首页必须可访问。

真实业务 Playwright 必须从外部客户端运行，使用受控 access code 完成登录、项目创建、教材上传、异步生成、刷新恢复和登出负测。不得在普通验证中调用真实 Provider。

## 回退

应用错误但数据完整时执行：

```bash
sudo /opt/shanhaiedu-production/current/infra/prod/rollback.sh
```

回退只重启上一版 API、Worker 和 Web 镜像，不降级数据库、不删除对象和业务事实。数据完整性或安全问题应停止入口并执行前向修复；不得盲目恢复旧数据库覆盖已确认写入。

首次 Nginx 切换失败由 `configure-host.sh` 的错误 trap 自动恢复。手工恢复时读取 `shared/nginx-backup/latest`，核对备份路径后恢复原 `image-studio-theme-qa-ip` 链接，并先运行 `nginx -t`。
