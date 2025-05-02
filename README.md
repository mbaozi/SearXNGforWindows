# SearXNG for Windows

[SearXNG 是一个免费的互联网元搜索引擎，它汇总了来自各种搜索服务和数据库的结果。用户既不会被跟踪，也不会被分析。](https://github.com/searxng/searxng)

SearXNG 可以部署在 Liunx 主机或 Docker 环境，虽基于 python 开发，但未适配 Windows 环境。

网络上查到的 Windows 环境部署 SearXNG 全是基于 WSL 的 Docker (Desktop)，或者是通过虚拟机。

本仓库通过修改 SearXNG 源码，无需通过 WSL 和 虚拟机，完美适配 Windows 环境，且仓库搭配好 Python 环境，可直接启动运行。



## 仓库介绍

**python**

> 基于 python-3.11.9-embed-amd64，已安装好 searxng 运行所需要的依赖包

**searx**

> 基于 SearXNG 2025.4.25+9ec9499d8，已修改适配 Windows 环境



### 直接使用

下载后直接执行 SearXNG for Windows.bat 或者 SearXNG for Windows.exe 可启动 SearXNG，默认访问路径

```http
http://localhost:8888
```

或

```http
http://127.0.0.1:8888
```



### 使用本地 python 环境

安装 searx/requirements.txt 中依赖包

```bash
pip install -r searx/requirements.txt
```

启动 SearXNG

```bash
python ./searx/webapp.py
```

访问路径同上

为了方便使用，默认禁用了大部分搜索引擎，仅保留了搜狗和百度，启动后可在首选项页面进行修改

> 其他使用事项可参考原仓库 https://github.com/searxng/searxng

