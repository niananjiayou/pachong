# 使用 Python 3.9 官方镜像（基于 Debian）
FROM python:3.9-slim-buster

# 设置工作目录
WORKDIR /app

# 安装系统依赖（Chromium 及其依赖库）
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libgconf-2-4 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxss1 \
    libxtst6 \
    chromium-browser \
    chromium-chromedriver \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个应用代码到容器
COPY . .

# 暴露端口（Render 会自动分配 $PORT 环境变量）
EXPOSE 10000

# 启动应用（Gunicorn）
# -w 3: 3个工作进程
# -b 0.0.0.0:$PORT: 绑定到 Render 提供的 PORT 环境变量（通常是 10000）
# app:app: 运行 app.py 中的 Flask 实例
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:$PORT", "app:app"]