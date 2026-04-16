# 使用 Python 3.9 官方镜像（基于 Debian Bullseye，比 Buster 更稳定）
FROM python:3.9-slim-bullseye

# 设置工作目录
WORKDIR /app

# 安装系统依赖（包括 Chromium 及其依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    unzip \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    ca-certificates \
    libu2f-udev \
    libvpx6 \
    libxkbcommon0 \
    chromium-browser \
    chromium-chromedriver \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个应用代码到容器
COPY . .

# 暴露端口
EXPOSE 10000

# 启动应用（Gunicorn）
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:$PORT", "--timeout", "120", "app:app"]
