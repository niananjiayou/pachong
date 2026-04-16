# 使用 Python 3.10 官方镜像（比 3.9 更新，兼容性更好）
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 更新 APT 索引并安装必要的系统依赖
# 分开安装可以提高成功率
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    gnupg \
    curl \
    wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 添加 Google Chrome 官方仓库
RUN curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | \
    tee /etc/apt/sources.list.d/google-chrome.list

# 再次更新 APT 索引
RUN apt-get update

# 安装 Google Chrome 和相关依赖
RUN apt-get install -y --no-install-recommends \
    google-chrome-stable \
    chromium-driver \
    fonts-liberation \
    libappindicator3-1 \
    libnss3 \
    libxss1 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libxss1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有应用代码
COPY . .

# 暴露端口
EXPOSE 10000

# 启动应用
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:$PORT", "app:app"]
