# py-auth

`py-auth` 是一个基于 FastAPI 的软件授权服务，包含：

- 授权服务接口（设备心跳、多产品策略）
- Web 管理后台
- 易支付对接与公开支付页
- Python / Go / TypeScript 客户端 SDK

适用于设备授权校验、付费授权、后台管理、操作审计和多语言客户端接入。

## 功能概览

- 设备注册与心跳校验（加密载荷，`client_secret` 解析产品）
- 多产品授权策略：默认、手动审核、付费
- 易支付：公开支付页、订单管理、支付回调
- 管理员登录与用户管理
- 操作日志审计与接口限流
- Web 管理后台（设备、产品、订单、易支付、系统配置）
- 支持 SQLite 和 MySQL

## 快速开始

### 方式一：Docker 运行

```bash
docker compose up -d
```

说明：

- 使用 [docker-compose.yaml](docker-compose.yaml)
- 默认使用 SQLite
- 数据持久化到 Docker 卷 `auth_data`
- 服务地址：`http://127.0.0.1:8000`
- 接口文档：`http://127.0.0.1:8000/docs`

### 方式二：本地运行

1. 创建并激活虚拟环境

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. 安装后端依赖

```powershell
pip install -e .
```

3. 准备环境变量

```powershell
Copy-Item env.example .env
```

4. 构建前端

```powershell
Set-Location web
pnpm install
pnpm build
Set-Location ..
```

5. 启动后端

```powershell
python main.py
```

说明：

- 本地运行默认地址：`http://127.0.0.1:8000`
- 接口文档：`http://127.0.0.1:8000/docs`
- 首次启动会自动创建数据库表，并按 `.env` 中的 `ADMIN_USERNAME`、`ADMIN_PASSWORD` 初始化管理员账号
- 如果未先构建前端，根路径只能返回后端状态信息，无法直接使用管理后台页面

## 运行模式

### 集成运行

适用于 Docker、部署环境或本地一体化运行。

- 访问入口：`http://127.0.0.1:8000`
- 后端直接托管 `web/dist`
- 本地一体化运行前需要先执行 `pnpm build`
- Docker 镜像构建时会自动完成前端构建

### 前端开发模式

适用于本地联调。

- 后端地址：`http://127.0.0.1:8000`
- 前端地址：`http://127.0.0.1:3000`
- Vite 会将 `/api` 代理到 `8000`
- Vite 会将 `/ws` 代理到 `ws://127.0.0.1:8000`

建议启动顺序：

1. 启动后端：`python main.py`
2. 进入 `web` 目录执行：`pnpm dev`

在该模式下，应访问 `http://127.0.0.1:3000` 调试前端页面。

## 环境变量

| 变量 | 说明 |
|------|------|
| `DATABASE_TYPE` | 数据库类型，`sqlite` 或 `mysql` |
| `SQLITE_PATH` | SQLite 文件路径 |
| `MYSQL_HOST` | MySQL 主机 |
| `MYSQL_PORT` | MySQL 端口 |
| `MYSQL_USER` | MySQL 用户名 |
| `MYSQL_PASSWORD` | MySQL 密码 |
| `MYSQL_DATABASE` | MySQL 数据库名 |
| `SECRET_KEY` | 服务端 JWT 密钥 |
| `CLIENT_SECRET` | 默认产品的 Client Secret（心跳加解密；未登记产品使用，须与客户端一致） |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 登录令牌过期时间（分钟） |
| `ADMIN_USERNAME` | 默认管理员用户名 |
| `ADMIN_PASSWORD` | 默认管理员密码 |
| `PUBLIC_BASE_URL` | 公网访问根地址，用于易支付回调与对外支付页链接，如 `https://auth.example.com` |
| `EPAY_API_URL` | 易支付接口地址（也可在后台配置） |
| `EPAY_PID` | 易支付商户 ID |
| `EPAY_KEY` | 易支付商户密钥 |
| `EPAY_NOTIFY_URL` | 易支付异步通知 URL，留空则自动生成 |
| `EPAY_RETURN_URL` | 易支付同步跳转 URL，留空则自动生成 |

示例见 [env.example](env.example)。

## 项目结构

```text
.
├─ app/                  FastAPI 服务端代码
├─ client/               多语言客户端 SDK
├─ docs/dev/             开发文档
├─ tools/                辅助工具脚本
├─ web/                  Web 管理后台
├─ main.py               服务入口
├─ docker-compose.yaml   Docker 编排文件
└─ Dockerfile            Docker 镜像构建文件
```

## 主要接口

### 客户端

- `POST /api/auth/heartbeat`：设备心跳与授权校验（加密请求）

### 公开支付

- `GET /api/payment/channels`：已开启的支付渠道
- `GET /api/payment/device-context?device_id=`：设备可支付信息
- `POST /api/payment/orders`：创建支付订单
- `GET /api/payment/orders/{out_trade_no}?device_id=`：查询订单（须设备 ID 匹配）
- `GET|POST /api/payment/epay/notify`：易支付异步通知
- `GET /api/payment/epay/return`：易支付同步跳转

公开页面：`/pay`（支付）、`/pay/result`（支付结果）

### 后台（需登录）

- `POST /api/user/login`：用户登录
- `GET /api/user/me`：当前用户信息

### 后台（需管理员）

- `GET/PUT /api/admin/config`：限流等系统配置
- `GET/POST/PUT/DELETE /api/admin/users`：用户管理
- `GET/DELETE /api/admin/logs`：操作日志
- `GET/POST/PUT/DELETE /api/admin/products`：产品管理
- `GET/PUT /api/admin/payment/epay`：易支付配置
- `GET /api/admin/payment/orders`：订单列表
- `WS /ws?token=`：设备列表实时更新（**仅管理员**）

## 管理后台

| 页面 | 路径 | 权限 |
|------|------|------|
| 概览 | `/overview` | 登录用户 |
| 设备管理 | `/devices` | 登录用户 |
| 产品管理 | `/products` | 管理员 |
| 订单管理 | `/orders` | 管理员 |
| 易支付 | `/epay` | 管理员 |
| 系统配置 | `/settings` | 管理员 |
| 用户管理 | `/users` | 管理员 |
| 审计日志 | `/audit-logs` | 管理员 |

前端开发：

```powershell
Set-Location web
pnpm install
pnpm dev
```

前端构建：

```powershell
Set-Location web
pnpm build
```

当 `web/dist` 存在时，后端会自动托管前端静态文件。

## 客户端 SDK

用户文档：

| 文档 | 说明 |
|------|------|
| [client/README.md](client/README.md) | 客户端 SDK 总览 |
| [client/python/README.md](client/python/README.md) | Python 客户端 SDK |
| [client/go/README.md](client/go/README.md) | Go 客户端 SDK |
| [client/ts/README.md](client/ts/README.md) | TypeScript 客户端 SDK |
| [web/src/docs/usage.md](web/src/docs/usage.md) | 管理后台字段说明 |

开发文档：

| 文档 | 说明 |
|------|------|
| [docs/dev/payment.md](docs/dev/payment.md) | 易支付、公网地址与支付流程 |
| [docs/dev/client-storage.md](docs/dev/client-storage.md) | 客户端本地存储与加解密约定 |
| [docs/dev/client-python-release.md](docs/dev/client-python-release.md) | Python 客户端构建与发布 |
| [docs/dev/client-ts-build.md](docs/dev/client-ts-build.md) | TypeScript 客户端构建说明 |

## 生产环境检查清单

- [ ] 替换 `SECRET_KEY`、`CLIENT_SECRET`、默认管理员密码
- [ ] 配置 `PUBLIC_BASE_URL` 为对外 HTTPS 域名
- [ ] 在后台或 `.env` 完成易支付商户配置并测试连接
- [ ] 确认后台展示的支付页、回调、跳转地址均为生产域名（非 `localhost`）
- [ ] 使用 HTTPS 反向代理，并正确传递 `X-Forwarded-Proto` / `Host`
- [ ] 为各产品配置 `client_secret` 与授权策略，客户端硬编码对应标识

## 备注

- 默认可以直接使用 SQLite 启动
- 仓库中的 `auth.db` 是本地开发数据库文件，勿用于生产
