import os
import json
import threading
from flask import Flask, request, jsonify, render_template, Response, send_from_directory
import json
from datetime import datetime

# 导入你的爬虫核心逻辑
from crawler_core import run_jd_crawler, log_queue, set_stop_event, clear_stop_event, crawler_logger

# 确保 Flask 日志也输出到控制台
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
flask_logger = logging.getLogger(__name__)

app = Flask(__name__)

# 用于跟踪爬虫线程，以便可以停止它
current_crawler_thread = None

# --- Flask 路由 ---

@app.route('/')
def index():
    """提供前端 HTML 页面"""
    return render_template('index.html')

@app.route('/crawl', methods=['POST'])
def crawl():
    try:
        data = request.get_json() # 获取前端发送的 JSON 数据
        item_id_or_url = data.get('productId') # 从数据中提取 productId

        if not item_id_or_url:
            return jsonify({"status": "error", "message": "请输入商品ID或链接！"}), 400
        
        default_browser_type = "edge"
        default_max_pages = 10
        crawler_logger.info(f"Flask后端接收到爬取请求，商品ID/链接: {item_id_or_url},"f"浏览器类型: {default_browser_type}, 最大页数: {default_max_pages}")

        # 调用爬虫核心函数
        # run_jd_crawler 返回 (bool, str)
        success, message = run_jd_crawler(
            browser_type=default_browser_type,
            product_input=item_id_or_url,
            max_pages=default_max_pages
        )

        if success:
            # 返回给前端的JSON结构，前端JS会检查 data.status
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"status": "error", "message": message})        
    

    except Exception as e:
        crawler_logger.error(f"爬虫请求处理失败: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"服务器内部错误: {str(e)}"}), 500

@app.route('/start_crawl', methods=['POST'])
def start_crawl():
    """
    处理启动爬虫的请求。
    在单独的线程中运行爬虫，以避免阻塞 Flask 主线程。
    """
    global current_crawler_thread

    if current_crawler_thread and current_crawler_thread.is_alive():
        return jsonify({'message': '爬虫正在运行中，请等待其完成或停止。'}), 400

    data = request.get_json()
    product_id = data.get('product_id')
    browser_type = data.get('browser_type')
    max_pages = 50 # 默认页数，或者从前端获取

    if not product_id or not browser_type:
        return jsonify({'message': '缺少商品ID或浏览器类型。'}), 400

    flask_logger.info(f"收到启动爬虫请求: 商品ID={product_id}, 浏览器={browser_type}")

    # 清除之前的停止事件，为新的爬取做准备
    clear_stop_event()

    # 在单独的线程中运行爬虫，这样主 Flask 线程可以继续处理其他请求 (例如日志流)
    current_crawler_thread = threading.Thread(
        target=_run_crawler_in_thread,
        args=(browser_type, product_id, max_pages)
    )
    current_crawler_thread.daemon = True # 设置为守护线程，主程序退出时自动终止
    current_crawler_thread.start()

    return jsonify({'message': '爬虫已启动。'}), 200

def _run_crawler_in_thread(browser_type, product_id, max_pages):
    """
    在单独的线程中执行爬虫的核心逻辑。
    将结果记录到日志，并通过 log_queue 传递。
    """
    try:
        # 清空队列，确保新任务不会看到旧日志
        while not log_queue.empty():
            log_queue.get()
        
        # 调用爬虫核心函数
        success, message = run_jd_crawler(
            browser_type=browser_type,
            product_input=product_id,
            max_pages=max_pages
        )
        if success:
            crawler_logger.info(f"✨ 爬取任务完成: {message}")
        else:
            crawler_logger.error(f"💥 爬取任务失败: {message}")
    except Exception as e:
        crawler_logger.error(f"❌ 爬虫线程发生未捕获错误: {e}")
        crawler_logger.error(traceback.format_exc())
    finally:
        # 爬虫任务结束后，发送一个结束信号到日志队列
        # 这样前端知道任务已完成，可以更新 UI
        crawler_logger.info("---CRAWL_TASK_END---")


@app.route('/stop_crawl', methods=['POST'])
def stop_crawl():
    """处理停止爬虫的请求。"""
    global current_crawler_thread

    if current_crawler_thread and current_crawler_thread.is_alive():
        flask_logger.info("收到停止爬虫请求。")
        set_stop_event() # 设置停止事件，通知爬虫停止
        return jsonify({'message': '停止爬虫请求已发送。'}), 200
    else:
        return jsonify({'message': '当前没有爬虫正在运行。'}), 400

@app.route('/log_stream')
def log_stream():
    """
    使用 Server-Sent Events (SSE) 实时推送日志到前端。
    """
    def generate_logs():
        while True:
            try:
                # 从队列中获取日志记录
                record = log_queue.get(timeout=1) # 1秒超时，避免无限等待
                
                # 检查特殊结束信号
                if record.message == "---CRAWL_TASK_END---":
                    yield f"data: {json.dumps({'message': '---CRAWL_TASK_END---', 'level': 'info'})}\n\n"
                    break # 结束日志流
                    
                # 将日志记录格式化为 JSON，并包含级别信息
                log_entry = {
                    'message': record.message.strip(),
                    'level': record.levelname.lower()
                }
                yield f"data: {json.dumps(log_entry)}\n\n"
            except queue.Empty:
                # 队列为空时，发送一个心跳包保持连接
                yield "data: heartbeat\n\n"
            except Exception as e:
                flask_logger.error(f"日志流生成器错误: {e}")
                break

            # 刷新输出缓冲区，确保数据及时发送
            # 这是关键，确保数据包及时到达前端
            # 但在Response中使用yield时，Flask会负责缓冲管理
            # 这里的sleep是为了减少CPU占用，以及避免在没有日志时频繁发送空数据
            time.sleep(0.1)

    return Response(generate_logs(), mimetype='text/event-stream')

# --- 静态文件服务 (如果index.html在templates外) ---
# app.route('/<path:filename>')
# def serve_static(filename):
#     root_dir = os.path.dirname(os.getcwd())
#     return send_from_directory(os.path.join(root_dir, 'static'), filename)


if __name__ == '__main__':
    # 检查 DrissionPage 是否安装
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError:
        flask_logger.error("DrissionPage 未安装。请运行 'pip install DrissionPage'。")
        import sys
        sys.exit(1)

    # 仅本地开发时运行
    app.run(debug=False, host='127.0.0.1', port=5000)
