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

需要创建以下目录结构：

```
www.geekery.cn/pip/
├── py_auth_client-0.1.0-py3-none-any.whl
├── py_auth_client-0.1.0.tar.gz
└── simple/
    └── py-auth-client/
        └── index.html  # 包索引文件
```

**重要**：必须创建 `simple/py-auth-client/` 目录，并在其中创建 `index.html` 文件，内容如下：

```html
<!DOCTYPE html>
<html>
<head><title>Links for py-auth-client</title></head>
<body>
<h1>Links for py-auth-client</h1>
<a href="../../py_auth_client-0.1.0-py3-none-any.whl">py_auth_client-0.1.0-py3-none-any.whl</a><br/>
<a href="../../py_auth_client-0.1.0.tar.gz">py_auth_client-0.1.0.tar.gz</a><br/>
</body>
</html>
```

### 注意事项

1. **版本管理**：保留历史版本文件，方便回滚
2. **索引**：简单静态服务不需要完整索引，pip可以直接从URL安装

## 从私有仓库安装

```bash
# 安装包（会从私有仓库查找包，依赖包从PyPI获取）
pip install py-auth-client --extra-index-url https://www.geekery.cn/pip/simple/

# 指定版本
pip install py-auth-client==0.1.0 --extra-index-url https://www.geekery.cn/pip/simple/
```

