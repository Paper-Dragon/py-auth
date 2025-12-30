# 构建和发布 py-auth-client

## 构建

```bash
# 安装构建工具
pip install build

# 进入client目录并构建
cd client
python -m build
```

构建完成后，会在 `dist/` 目录下生成分发包文件。

## 部署到私有仓库

构建完成后，将 `dist/` 目录下的文件上传到 `www.geekery.cn/pip/` 目录。

### 目录结构

```
www.geekery.cn/pip/
├── py_auth_client-0.1.0-py3-none-any.whl
├── py_auth_client-0.1.0.tar.gz
└── simple/  # 可选，用于包索引
    └── py-auth-client/
        └── index.html
```

### 注意事项

1. **版本管理**：保留历史版本文件，方便回滚
2. **索引**：简单静态服务不需要完整索引，pip可以直接从URL安装

## 从私有仓库安装

```bash
# 安装包
pip install py-auth-client --index-url https://www.geekery.cn/pip/simple/

# 指定版本
pip install py-auth-client==0.1.0 --index-url https://www.geekery.cn/pip/simple/
```

