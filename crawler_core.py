import sys  
import time  
import os  
import traceback  
import logging  
import json  
import csv  
import queue  
import threading  
import platform  
from urllib.parse import urlencode, parse_qs, unquote_plus, unquote  

from DrissionPage import ChromiumOptions, ChromiumPage  


# ===================== 日志 =====================  
log_queue = queue.Queue()  


class QueueHandler(logging.Handler):  
    def emit(self, record):  
        self.format(record)  
        log_queue.put(record)  


crawler_logger = logging.getLogger("crawler_logger")  
crawler_logger.setLevel(logging.INFO)  
crawler_logger.propagate = False  
if crawler_logger.handlers:  
    crawler_logger.handlers.clear()  

queue_handler = QueueHandler()  
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")  
queue_handler.setFormatter(formatter)  
crawler_logger.addHandler(queue_handler)  

stream_handler = logging.StreamHandler(sys.stdout)  
stream_handler.setFormatter(formatter)  
crawler_logger.addHandler(stream_handler)  

# ===================== 全局停止标记 =====================  
stop_event = threading.Event()  


def set_stop_event():  
    stop_event.set()  


def clear_stop_event():  
    stop_event.clear()  


def check_for_stop():  
    return stop_event.is_set()  


# ===================== 路径查找 =====================  
def find_chrome_path():  
    """在 Windows 本地和 Linux 云环境中查找 Chrome 浏览器"""  
    # 检测环境  
    is_linux = platform.system() == "Linux"  
    
    if is_linux:  
        # Render 云环境：使用系统 Chromium  
        chromium_path = "/usr/bin/chromium"
        if os.path.exists(chromium_path):
            crawler_logger.info("   🌐 检测到 Linux 环境（Render），使用系统 Chromium")  
            return chromium_path
        return None  
    
    # Windows 本地环境  
    paths = [  
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",  
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",  
    ]  
    for path in paths:  
        if os.path.exists(path):  
            return path  
    return None  


def find_edge_path():  
    """在 Windows 本地查找 Edge 浏览器，Render 上使用 Chromium"""  
    is_linux = platform.system() == "Linux"  
    
    if is_linux:  
        # Render 云环境：使用 Chromium 替代 Edge  
        chromium_path = "/usr/bin/chromium"
        if os.path.exists(chromium_path):
            crawler_logger.info("   🌐 检测到 Linux 环境（Render），使用系统 Chromium 替代 Edge")  
            return chromium_path
        return None  
    
    # Windows 本地环境  
    paths = [  
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",  
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",  
    ]  
    for path in paths:  
        if os.path.exists(path):  
            return path  
    return None    


def find_webdriver_path(browser_type):  
    """查找 WebDriver 驱动程序"""  
    is_linux = platform.system() == "Linux"  
    
    if is_linux:  
        # Render 云环境：让 DrissionPage 自动处理  
        crawler_logger.info("   🌐 Render 环境不需要 WebDriver 文件")  
        return None  
    
    if getattr(sys, "frozen", False):  
        current_app_dir = os.path.dirname(sys.executable)  
    else:  
        current_app_dir = os.path.dirname(os.path.abspath(__file__))  

    webdriver_name = "msedgedriver.exe" if browser_type.lower() == "edge" else "chromedriver.exe"  
    webdriver_path_in_bundle = os.path.join(current_app_dir, webdriver_name)  

    if os.path.exists(webdriver_path_in_bundle):  
        return webdriver_path_in_bundle  
    return None  


# ===================== 解析/提取工具 =====================  
def safe_json_loads(x):  
    try:  
        if x is None:  
            return None  
        if isinstance(x, (bytes, bytearray)):  
            x = x.decode("utf-8", errors="ignore")  
        if isinstance(x, str):  
            x = x.strip()  
            if not x:  
                return None  
            return json.loads(x)  
        if isinstance(x, dict):  
            return x  
    except Exception:  
        return None  
    return None  


def extract_resp_body(packet):  
    resp = getattr(packet, "response", None)  
    if resp is not None:  
        b = getattr(resp, "body", None)  
        if b is not None:  
            return b  
        rb = getattr(resp, "raw_body", None)  
        if rb is not None:  
            return rb  
    b2 = getattr(packet, "body", None)  
    if b2 is not None:  
        return b2  
    rb2 = getattr(packet, "raw_body", None)  
    if rb2 is not None:  
        return rb2  
    return None  


def parse_postdata_to_dict(req_post):  
    """  
    DrissionPage 的 req.postData 通常是 x-www-form-urlencoded 字符串/bytes  
    """  
    if req_post is None:  
        return None  
    try:  
        if isinstance(req_post, (bytes, bytearray)):  
            req_post = req_post.decode("utf-8", errors="ignore")  
        if not isinstance(req_post, str):  
            req_post = str(req_post)  
        post_dict = parse_qs(req_post, keep_blank_values=True)  
        return {k: v[0] for k, v in post_dict.items()}  
    except Exception:  
        return None  


def decode_body_json_from_post_single(post_single):  
    """  
    body 通常是 urlencoded 的 JSON，且可能出现 double-encode  
    """  
    if not post_single or "body" not in post_single:  
        return None  
    body_val = post_single.get("body")  
    if body_val is None:  
        return None  

    try:  
        if isinstance(body_val, (bytes, bytearray)):  
            body_val = body_val.decode("utf-8", errors="ignore")  
        if not isinstance(body_val, str):  
            body_val = str(body_val)  

        candidates = [body_val, unquote_plus(body_val), unquote(body_val)]  
        more = []  
        for c in candidates[:]:  
            try:  
                more.append(unquote_plus(c))  
            except Exception:  
                pass  
            try:  
                more.append(unquote(c))  
            except Exception:  
                pass  
        candidates.extend(more)  

        for c in candidates:  
            c = c.strip()  
            if not c:  
                continue  
            try:  
                return json.loads(c)  
            except Exception:  
                continue  
    except Exception:  
        return None  
    return None  


def contains_commentinfo(obj, depth=0):  
    """  
    只判断是否存在 commentInfo（用于过滤接口）  
    """  
    if depth > 16:  
        return False  
    if isinstance(obj, dict):  
        if "commentInfo" in obj:  
            return True  
        for v in obj.values():  
            if contains_commentinfo(v, depth + 1):  
                return True  
    elif isinstance(obj, list):  
        for it in obj[:500]:  
            if contains_commentinfo(it, depth + 1):  
                return True  
    return False  


def extract_all_commentinfo(obj, depth=0):  
    """  
    把所有 commentInfo dict 收集出来  
    """  
    results = []  
    if depth > 16:  
        return results  

    if isinstance(obj, dict):  
        if isinstance(obj.get("commentInfo"), dict):  
            results.append(obj["commentInfo"])  
        for v in obj.values():  
            results.extend(extract_all_commentinfo(v, depth + 1))  
    elif isinstance(obj, list):  
        for it in obj[:800]:  
            results.extend(extract_all_commentinfo(it, depth + 1))  
    return results  


def extract_func_id_from_url(url: str):  
    try:  
        if url and "functionId=" in url:  
            return url.split("functionId=", 1)[-1].split("&", 1)[0]  
    except Exception:  
        pass  
    return None  


def scroll_autodetect_and_bottom(page: ChromiumPage, step: int = 900):  
    js = f"""  
    (() => {{  
      function isScrollable(el){{  
        if(!el) return false;  
        const cs = window.getComputedStyle(el);  
        const overflowY = cs.overflowY;  
        const canScroll = (el.scrollHeight - el.clientHeight) > 50;  
        return canScroll && (overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay' || overflowY === 'hidden' || true);  
      }}  

      const candidates = [];  
      const sc = document.querySelector('div[data-virtuoso-scroller="true"]');  
      if(sc) candidates.push({{el: sc, name: 'virtuoso_scroller'}});  

      const box = document.querySelector('[class*="rateListContainer_"]');  
      if(box) candidates.push({{el: box, name: 'rateListContainer'}});  

      // 有些页面把滚动条放在更外层包裹元素，尽量再找一层  
      const box2 = document.querySelector('[class*="rateListBox_"]');  
      if(box2) candidates.push({{el: box2, name: 'rateListBox'}});  

      // 从候选里挑真正 scrollHeight/clientHeight 满足的那个（差值最大）  
      let best = null;  
      let bestScore = -1;  

      for(const c of candidates){{  
        const el = c.el;  
        if(!el) continue;  
        const score = (el.scrollHeight - el.clientHeight);  
        if(isScrollable(el) && score > bestScore){{  
          best = c;  
          bestScore = score;  
        }}  
      }}  

      // 兜底：遍历一些常见滚动容器（避免只靠固定选择器）  
      if(!best){{  
        const all = Array.from(document.querySelectorAll('div,section,main,article'));  
        for(const el of all){{  
          if(isScrollable(el)){{  
            const score = (el.scrollHeight - el.clientHeight);  
            if(score > bestScore){{  
              bestScore = score;  
              best = {{el, name: 'fallback_scrollable'}};  
            }}  
          }}  
        }}  
      }}  

      if(!best){{  
        return JSON.stringify({{ok:false, reason:'no_scrollable_found'}});  
      }}  

      const el = best.el;  
      const before = el.scrollTop;  

      const max = Math.max(0, el.scrollHeight - el.clientHeight);  
      const target = Math.min(max, before + {step});  
      el.scrollTop = target;  

      // 触发事件（有的组件监听 scroll，有的监听 wheel）  
      el.dispatchEvent(new Event('scroll', {{bubbles:true}}));  
      el.dispatchEvent(new WheelEvent('wheel', {{deltaY:{step}, bubbles:true}}));  
      // 聚焦有时也能触发某些监听  
      try {{ el.focus && el.focus(); }} catch(e) {{}}  

      const after = el.scrollTop;  
      return JSON.stringify({{  
        ok:true,  
        chosen: best.name,  
        scrollTop_before: before,  
        scrollTop_after: after,  
        maxScroll: max,  
        delta: after - before  
      }});  
    }})()  
    """  
    raw = page.run_js(js, as_expr=False)  
    if raw is None:  
        return {"ok": False, "reason": "js_return_is_none"}  

    # 统一成 dict  
    try:  
        if isinstance(raw, str):  
            return json.loads(raw)  
        # 有些情况下直接返回对象/字典  
        return raw  
    except Exception:  
        return {"ok": False, "reason": "parse_return_failed", "raw": raw}  


# ===================== 主函数 =====================  
def run_jd_crawler(  
    browser_type: str,  
    product_input: str,  
    max_pages: int,  
    browser_path: str = None,  
    keep_browser_open_on_fail: bool = True,   # ✅ 失败/停止/异常时不关浏览器  
    max_rounds_factor: int = 3,               # 每"page"允许最多滚动轮数  
):  
    crawler_logger.info("\n" + "=" * 60)  
    crawler_logger.info(f"🚀 开始爬取京东评论 ({browser_type})")  
    crawler_logger.info(f"商品ID/链接: {product_input}, 目标页数上限 max_pages={max_pages}")  
    crawler_logger.info("=" * 60 + "\n")  

    clear_stop_event()  
    all_reviews = []  
    output_file = f"评论_{product_input.split('/')[-1].replace('.html', '')}.csv"  

    page = None  
    success = False  
    exception_happened = False  
    user_stopped = False  

    seen_comment_ids = set()  
    seen_page_nums = set()  
    max_seen_page_num = 0  

    # 用于"连续无新增"判定  
    empty_rounds = 0  
    max_empty_rounds = 6  

    try:  
        # ===== 商品ID =====  
        if product_input.startswith("http"):  
            product_id = product_input.split("/")[-1].replace(".html", "")  
        else:  
            product_id = product_input  

        # ===== 配置浏览器 =====  
        crawler_logger.info(f"📍 第1步：配置 {browser_type} 路径和 WebDriver...")  
        co = ChromiumOptions()  

        APP_DIR = os.path.dirname(os.path.abspath(__file__))  
        is_linux = platform.system() == "Linux"  

        # ⭐ 关键改动：针对不同环境设置用户数据目录  
        if is_linux:  
            # Render 云环境：使用临时目录  
            user_data_dir = "/tmp/jd_profile"  
        else:  
            # Windows 本地：使用项目目录  
            user_data_dir = os.path.join(APP_DIR, "browser_data", "jd_profile")  

        os.makedirs(user_data_dir, exist_ok=True)  

        co.set_argument(f'--user-data-dir={user_data_dir}')  
        co.set_argument('--profile-directory=Default')  

        if browser_path and os.path.exists(browser_path):  
            co.set_browser_path(browser_path)  
            crawler_logger.info(f"   使用用户提供的浏览器路径: {browser_path}")  
        else:  
            auto_path = find_edge_path() if browser_type.lower() == "edge" else find_chrome_path()  
            if auto_path and os.path.exists(auto_path):  
                co.set_browser_path(auto_path)  
                crawler_logger.info(f"   自动检测到浏览器路径: {auto_path}")  
            elif not is_linux:  
                # 只在本地环境报错  
                crawler_logger.error(f"❌ 未能找到 {browser_type} 浏览器可执行文件。")  
                return False, f"未能找到 {browser_type} 浏览器可执行文件。"  
            else:  
                # Render 上会自动使用系统 Chromium  
                crawler_logger.info("   将使用系统默认浏览器（Chromium）")  

        webdriver_path = find_webdriver_path(browser_type)  
        if webdriver_path:  
            crawler_logger.info(f"   使用 WebDriver 路径: {webdriver_path}")  
        else:  
            crawler_logger.warning("   未能找到驱动文件。DrissionPage 将尝试默认逻辑。")  

        co.set_local_port(9333)  
        co.set_argument("--disable-blink-features=AutomationControlled")  

        co.set_local_port(9333)  
        co.set_argument("--disable-blink-features=AutomationControlled")
        
        # ⭐ Render 环境特有参数
        if is_linux:
            co.set_argument("--headless")
            co.set_argument("--no-sandbox")
            co.set_argument("--disable-gpu")
            co.set_argument("--disable-dev-shm-usage")
            co.set_browser_path("/usr/bin/chromium")  # 🔥 明确指定 Chromium 路径
            crawler_logger.info("   ✅ 使用系统 Chromium 浏览器: /usr/bin/chromium")
 

        if browser_type.lower() == "edge":  
            co.set_argument(  
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "  
                "AppleWebKit/537.36 (KHTML, like Gecko) "  
                "Chrome/91.0.4472.124 Safari/537.36 "  
                "Edg/91.0.864.59"  
            )  
        elif browser_type.lower() == "chrome":  
            co.set_argument(  
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "  
                "AppleWebKit/537.36 (KHTML, like Gecko) "  
                "Chrome/91.0.4472.124 Safari/537.36"  
            )  

        crawler_logger.info(f"✅ {browser_type} 配置已完成\n")  

        # ===== 启动浏览器 =====  
        crawler_logger.info(f"📍 第2步：启动 {browser_type} 浏览器...")  
        try:  
            page = ChromiumPage(co, timeout=120)  
            crawler_logger.info(f"✅ {browser_type} 浏览器已启动\n")  
        except Exception as e:  
            crawler_logger.error(f"❌ 浏览器启动失败: {e}")  
            crawler_logger.error(traceback.format_exc())  
            return False, str(e)  

        # ===== Cookies =====  
        COOKIES_FILE = "jd_cookies.json"  
        if os.path.exists(COOKIES_FILE):  
            crawler_logger.info("📍 第2.5步：加载 Cookies...")  
            try:  
                with open(COOKIES_FILE, "r", encoding="utf-8") as f:  
                    cookies = json.load(f)  
                page.set.cookies(cookies)  
                crawler_logger.info("✅ Cookies 已加载\n")  
            except Exception as e:  
                crawler_logger.warning(f"❌ Cookies 加载失败: {e}\n")  

        # ===== 打开页面 =====  
        url = f"https://item.jd.com/{product_id}.html"  
        crawler_logger.info("📥 打开页面: %s", url)  

        # 建议：从打开页面就开始 listen，避免漏接口  
        page.listen.start()  

        page.get(url, timeout=30)  
        time.sleep(3)  
        crawler_logger.info("✅ 页面加载完成\n")  

        # 登录检测（简单兜底）  
        if "passport.jd.com" in page.url:  
            crawler_logger.warning("⚠️ 检测到需要登录，请手动完成登录（最多 5 分钟）...")  
            start_login_wait = time.time()  
            while "passport.jd.com" in page.url and (time.time() - start_login_wait < 300):  
                if check_for_stop():  
                    user_stopped = True  
                    return False, "用户中止爬取。"  
                time.sleep(5)  
            if "passport.jd.com" in page.url:  
                return False, "用户未在规定时间内完成登录。"  
            try:  
                cookies = page.cookies()  
                with open(COOKIES_FILE, "w", encoding="utf-8") as f:  
                    json.dump(cookies, f, ensure_ascii=False)  
            except Exception:  
                pass  

        # ===== 点击全部评价 =====
        crawler_logger.info("🔍 寻找评论按钮并点击...")
        time.sleep(4)  # 增加加载时间
        
        found_comment_button = False
        selectors = [
            "text=全部评价",
            "text=全部",
            ".comment-tab",
            "[data-tab='comment']",
        ]
        
        for sel in selectors:
            if check_for_stop():
                user_stopped = True
                return False, "用户中止爬取。"
            
            try:
                crawler_logger.info(f"   尝试选择器: {sel}")
                btn = page.ele(sel, timeout=5)
                if btn:
                    btn.scroll.to_see()
                    time.sleep(1.5)
                    btn.click()
                    crawler_logger.info(f"✅ 已点击评论按钮 (selector: {sel})\n")
                    found_comment_button = True
                    break
            except Exception as e:
                crawler_logger.info(f"   失败: {str(e)[:50]}")
                continue

        if not found_comment_button:
            # 尝试 JS 点击
            crawler_logger.warning("⚠️ 传统方法失败，尝试 JS 点击...")
            try:
                page.run_js("""
                    let clicked = false;
                    const commentTabs = document.querySelectorAll('.comment-tab a');
                    for(let tab of commentTabs){
                        const text = tab.textContent.trim();
                        if(text.includes('全部') || text === '全部评价'){
                            tab.click();
                            console.log('点击成功：' + text);
                            clicked = true;
                            break;
                        }
                    }
                    if(!clicked){
                        const dataTabs = document.querySelectorAll('[data-tab="comment"]');
                        for(let tab of dataTabs){
                            tab.click();
                            console.log('点击成功：data-tab');
                            clicked = true;
                            break;
                        }
                    }
                    if(!clicked){
                        const allLinks = document.querySelectorAll('a');
                        for(let link of allLinks){
                            const text = link.textContent.trim();
                            if(text.includes('全部') && text.includes('评')){
                                link.click();
                                console.log('点击成功：' + text);
                                clicked = true;
                                break;
                            }
                        }
                    }
                    return clicked;
                """)
                time.sleep(2)
                found_comment_button = True
                crawler_logger.info("✅ 已通过 JS 点击评论按钮\n")
            except Exception as e:
                crawler_logger.error(f"❌ JS 点击也失败: {e}")

        if not found_comment_button:
            crawler_logger.error("❌ 未找到评论按钮。")
            return False, "未能找到评论按钮，无法继续爬取。"

        crawler_logger.info("⏳ 等待评论区接口开始（约 8 秒）...")
        time.sleep(8)


        # --------------- 自动滚动翻页 ---------------  
        crawler_logger.info("🌀 开始自动滚动翻页（Virtuoso scroller 触发请求）")  

        max_rounds = max_pages * max_rounds_factor + 10  
        rounds = 0  

        def try_extract_from_response(resp_packet):  
            """  
            从 page.listen 的 resp_packet 中提取评论，并返回新增数量（added）  
            """  
            raw_body = extract_resp_body(resp_packet)  
            resp_data = safe_json_loads(raw_body)  
            if resp_data is None:  
                return 0, None  

            if not contains_commentinfo(resp_data):  
                return 0, None  

            req = getattr(resp_packet, "request", None)  
            req_url = str(getattr(req, "url", "") or "")  
            resp_url = str(getattr(getattr(resp_packet, "response", None), "url", "") or "")  
            full_url = resp_url or req_url  

            func_id = extract_func_id_from_url(full_url)  

            # 尽力解析 pageNum  
            req_post = getattr(req, "postData", None)  
            post_single = parse_postdata_to_dict(req_post)  
            body_json = decode_body_json_from_post_single(post_single) if post_single else None  
            page_num = None  
            if isinstance(body_json, dict):  
                pn = body_json.get("pageNum", None)  
                try:  
                    if pn is not None:  
                        page_num = int(str(pn))  
                except Exception:  
                    page_num = None  

            comment_infos = extract_all_commentinfo(resp_data)  
            added = 0  

            for ci in comment_infos:  
                if not isinstance(ci, dict):  
                    continue  

                cid = ci.get("commentId")  
                comment_date = ci.get("commentDate", "")  
                comment_data = ci.get("commentData", "")  
                nickname = ci.get("userNickName", "")  

                if cid:  
                    key = cid  
                else:  
                    key = f"{nickname}_{comment_date}_{comment_data[:40]}"  

                if key in seen_comment_ids:  
                    continue  
                seen_comment_ids.add(key)  

                rating = ci.get("commentScore", 0)  
                try:  
                    rating = int(str(rating))  
                except Exception:  
                    rating = 0  

                likes = ci.get("usefulVoteCount", None)  
                if likes is None:  
                    likes = ci.get("praiseCnt", 0)  
                try:  
                    likes = int(str(likes))  
                except Exception:  
                    likes = 0  

                product_model = ""  
                wa = ci.get("wareAttribute")  
                if isinstance(wa, list) and wa:  
                    try:  
                        product_model = ",".join([str(item) for item in wa])  
                    except Exception:  
                        product_model = str(wa)  

                all_reviews.append(  
                    {  
                        "review_content": comment_data,  
                        "rating": rating,  
                        "review_time": comment_date,  
                        "product_model": product_model,  
                        "likes": likes,  
                    }  
                )  
                added += 1  

            return added, (func_id, page_num)  

        while rounds < max_rounds:  
            if check_for_stop():  
                user_stopped = True  
                return False, "用户中止爬取。"  

            rounds += 1  

            before_total = len(all_reviews)  

            # 1) 滚到底触发下一批虚拟渲染  
            try:  
                scroller_info = scroll_autodetect_and_bottom(page, step=900)  
                crawler_logger.info(f"🌀 滚动触发(round={rounds}): {scroller_info}")  
            except Exception as e:  
                crawler_logger.warning(f"滚动失败(round={rounds}): {e}")  

            # 2) 等待一段时间收集可能的评论接口返回  
            wait_time = 1.3  
            t_end = time.time() + wait_time  

            added_this_round = 0  
            new_page_num_seen = None  

            while time.time() < t_end:  
                if check_for_stop():  
                    user_stopped = True  
                    return False, "用户中止爬取。"  

                resp = page.listen.wait(timeout=0.5)  
                if not resp:  
                    continue  

                req = getattr(resp, "request", None)  
                req_method = str(getattr(req, "method", "") or "").upper()  

                # Virtuoso 拉取通常是 POST/XHR；这里不硬性限制，只保留一定稳定性  
                # 你之前抓不到 getCommentListPage 的情况可能是过滤条件过严  
                if req_method not in ("POST", "PUT", "GET", ""):  
                    continue  

                # 只要 response 里有 commentInfo 就解析  
                try:  
                    added, meta = try_extract_from_response(resp)  
                    if added > 0:  
                        added_this_round += added  
                        if meta:  
                            func_id, page_num = meta  
                            if page_num is not None:  
                                seen_page_nums.add(page_num)  
                                new_page_num_seen = page_num  
                            crawler_logger.info(  
                                f"✅ 命中评论接口(可能): func_id={meta[0]} pageNum={meta[1]} 本轮新增 {added} | 累计 {len(all_reviews)}"  
                            )  
                except Exception:  
                    # 单条包解析失败不影响主循环  
                    pass  

            # 3) 判断是否达到目标页数  
            if new_page_num_seen is not None and new_page_num_seen > max_seen_page_num:  
                max_seen_page_num = new_page_num_seen  

            # 4) 连续无新增判定  
            after_total = len(all_reviews)  
            if after_total == before_total:  
                empty_rounds += 1  
                crawler_logger.warning(  
                    f"⚠️ 本轮无新增评论(round={rounds}) empty_rounds={empty_rounds}/{max_empty_rounds}"  
                )  
            else:  
                empty_rounds = 0  
                crawler_logger.info(  
                    f"📌 本轮新增成功(round={rounds}): 新增 {after_total - before_total} | 总计 {after_total}"  
                )  

            # 5) 达到 max_pages 则停止（pageNum 可解析时）  
            if max_seen_page_num >= max_pages and max_seen_page_num > 0:  
                crawler_logger.info(f"🎉 已达到目标页数：max_seen_page_num={max_seen_page_num} >= {max_pages}")  
                break  

            if empty_rounds >= max_empty_rounds:  
                crawler_logger.info(f"✅ 连续 {max_empty_rounds} 轮无新增，停止自动翻页")  
                break  

            time.sleep(0.6)  

        # 停止监听  
        try:  
            page.listen.stop()  
        except Exception:  
            pass  

        # --------------- 保存 CSV ---------------  
        if not all_reviews:  
            crawler_logger.warning("⚠️ 没有爬取到任何评论数据")  
            return False, "没有爬取到任何评论数据"  

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:  
            writer = csv.DictWriter(  
                f,  
                fieldnames=["review_content", "rating", "review_time", "product_model", "likes"],  
            )  
            writer.writeheader()  
            writer.writerows(all_reviews)  

        crawler_logger.info("\n🎉 数据已保存！")  
        crawler_logger.info(f"📊 共爬取: {len(all_reviews)} 条评论")  
        crawler_logger.info(f"💾 文件已保存: {os.path.abspath(output_file)}\n")  

        success = True  
        return True, f"爬取完成！共 {len(all_reviews)} 条评论，保存到 {os.path.abspath(output_file)}"  

    except Exception as e:  
        exception_happened = True  
        crawler_logger.error(f"❌ 爬虫执行出错: {e}")  
        crawler_logger.error(traceback.format_exc())  
        return False, f"爬虫执行过程中发生错误: {str(e)}"  
    finally:
        if page is not None:
            should_keep_open = keep_browser_open_on_fail and (not success or user_stopped or exception_happened)
            if should_keep_open:
                crawler_logger.warning(
                    "🛑 由于任务失败/停止/异常，浏览器不会自动关闭以便你排查。"
                    "请手动关闭浏览器窗口。"
                )
                # 这里不 quit
            else:
                try:
                    page.quit()
                    crawler_logger.info("✅ 浏览器已关闭。")
                except Exception:
                    pass
