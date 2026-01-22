## Docker基础

Docker 是一个容器化平台，用于开发、部署和运行应用程序，它将应用程序及其所有依赖项打包到一个可移植的容器中。。

### 核心概念

- 容器 (Container)：轻量级、可执行的软件包，包含运行应用程序所需的一切：代码、运行时、系统工具、库和设置
- 镜像（Image）：容器的只读模板；包含创建容器所需的所有文件和配置
- Dockerfile：用于构建镜像的文本文件，包含一系列指令来定义如何创建镜像

### 常用命令

```bash
# 拉取镜像(从默认docker镜像下载)
docker pull nginx

# 如果有访问问题，可以使用国内镜像库
docker pull docker.m.daocloud.io/nginx

# 运行容器
docker run -d -p 80:80 nginx

# 查看运行中的容器
docker ps

# 查看所有容器
docker ps -a

# 进入镜像
docker exec -it <container_id> bash

# 停止容器
docker stop container_id

# 删除容器
docker rm container_id

# 构建镜像
docker build -t my-app .

# 查看镜像
docker images

# 删除镜像
docker rmi <image_id>
```

### 模型管理

```bash
# 保存镜像到文件
docker save -o nginx.tar nginx:latest

# 或者使用重定向
docker save nginx:latest > nginx.tar

# 从文件加载镜像
docker load -i nginx.tar

# 或者使用重定向
docker load < nginx.tar

# 静默模式加载
docker load -q -i nginx.tar
```

### Dockerfile基础命令

```Dockerfile
# 使用
FROM ubuntu:22.04

# 设置元数据
LABEL description="pytorch on ascend"

# 设置环境变量
ENV APP_HOME=/app


# 设置工作目录
WORKDIR $APP_HOME

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt


RUN groupadd -r appuser && useradd -r -g appuser appuser

# 复制应用代码
COPY . .

# 更改文件所有者
RUN chown -R appuser:appuser $APP_HOME

# 切换到应用用户
USER appuser

# 声明端口
EXPOSE 5000


# 启动命令
CMD ["python", "train.py"]


```
