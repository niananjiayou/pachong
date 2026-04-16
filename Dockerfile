FROM python:3.9-slim-bullseye

WORKDIR /app

# 第1步：安装基础工具和 GPG 密钥管理
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 第2步：添加 Google Chrome 官方仓库
RUN curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# 第3步：安装 Google Chrome 和必要的库（不安装 chromium）
RUN apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable \
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
    libu2f-udev \
    libvpx6 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# 第4步：复制并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 第5步：复制应用代码
COPY . .

EXPOSE 10000

CMD gunicorn -w 1 -b 0.0.0.0:${PORT:-10000} --timeout 120 app:app
