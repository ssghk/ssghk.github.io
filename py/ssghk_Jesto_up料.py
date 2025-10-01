# *- coding: utf-8 -*-

# 取料
import requests
from bs4 import BeautifulSoup
import time
import random
import re
import json
from datetime import datetime, timedelta

#up料
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore



from google.colab import userdata

firebase_key_str = userdata.get('k.json')
firebase_key = json.loads(firebase_key_str)

# 新增：检查是否已更新过
def check_if_updated_today(集合名, 文檔ID):
    # 初始化Firebase应用
    cred = credentials.Certificate(firebase_key)  # 替换为你的K路径
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)

    # 获取当前日期
    今日日期 = datetime.now().strftime('%Y-%m-%d')

    # 检查文档
    db = firestore.client()
    doc_ref = db.collection(集合名).document(文檔ID)
    doc = doc_ref.get()

    if doc.exists:
        最后更新日期 = doc.to_dict().get('更新日期', '')
        return 最后更新日期 == 今日日期
    return False




# 取料
def jetsoclub_crawler(main_url):
    # 設置請求頭，模擬瀏覽器訪問
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
    }

    # 計算10天後的日期
    today = datetime.now()
    expire_date = (today + timedelta(days=10)).strftime('%Y-%m-%d')

    try:
        # 獲取主頁內容
        print("正在訪問主頁...")
        response = requests.get(main_url, headers=headers, timeout=10)
        response.raise_for_status()  # 檢查請求是否成功
        print("成功獲取主頁內容")

        # 解析HTML內容
        soup = BeautifulSoup(response.content, 'html.parser')

        # 查找所有可能的文章容器
        articles = []

        # 方法1: 嘗試直接查找所有文章標題連結
        print("嘗試方法1: 直接查找所有文章標題連結")
        all_article_links = soup.select('h3.entry-title a, h2.entry-title a, .post-title a, .post h3 a, .post h2 a')
        print(f"找到 {len(all_article_links)} 個可能的文章連結")

        for link in all_article_links:
            title = link.get_text(strip=True)
            href = link.get('href')
            if title and href and 'jetsoclub.com' in href:
                articles.append({'title': title, 'url': href, 'source': 'direct'})
                print(f"找到文章: {title}")

        # 方法2: 嘗試查找特定的容器
        print("嘗試方法2: 查找特定容器")
        for i in range(1, 6):  # 檢查前5個div
            container = soup.select_one(f'#Blog1 > div.blog-posts.hfeed > div:nth-child({i})')
            if container:
                print(f"找到容器 div[{i}]")
                article_links = container.select('h3.entry-title a, h2.entry-title a, a[href*="jetsoclub.com"]')
                for link in article_links:
                    title = link.get_text(strip=True)
                    href = link.get('href')
                    if title and href and 'jetsoclub.com' in href:
                        articles.append({'title': title, 'url': href, 'source': f'div{i}'})
                        print(f"找到文章: {title}")

        # 方法3: 查找所有帶有文章特徵的div
        print("嘗試方法3: 查找所有帶有文章特徵的div")
        post_containers = soup.select('.post-outer-container, .post, .hentry, .blog-post')
        print(f"找到 {len(post_containers)} 個文章容器")

        for container in post_containers:
            title_elem = container.select_one('h3.entry-title, h2.entry-title, .post-title, h3 a, h2 a')
            if title_elem:
                title = title_elem.get_text(strip=True)
                href = title_elem.get('href') if title_elem.name == 'a' else container.select_one('a').get('href') if container.select_one('a') else None
                if title and href and 'jetsoclub.com' in href:
                    articles.append({'title': title, 'url': href, 'source': 'post-container'})
                    print(f"找到文章: {title}")

        # 去除重複文章
        unique_articles = []
        seen_urls = set()
        for article in articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)

        print(f"總共找到 {len(unique_articles)} 篇唯一文章")

        if len(unique_articles) == 0:
            print("未找到任何文章")
            # 返回空的JSON數組
            print("json = []")
            return []

        # 遍歷每篇文章，獲取圖片連結
        results = []
        for i, article in enumerate(unique_articles):
            print(f"處理第 {i+1}/{len(unique_articles)} 篇文章 (來自 {article['source']}): {article['title']}")

            try:
                # 訪問文章頁面
                article_response = requests.get(article['url'], headers=headers, timeout=10)
                article_response.raise_for_status()

                # 解析文章內容
                article_soup = BeautifulSoup(article_response.content, 'html.parser')

                # 查找圖片 - 嘗試多種選擇器以適應不同文章結構
                img_selectors = [
                    'div[id^="post-body-"] div a img',
                    'div.post-body.entry-content div a img',
                    'div.entry-content div a img',
                    'div.separator a img',
                    'a img[src*="blogspot.com"]',
                    'a img[src*="bp.blogspot.com"]'
                ]

                img_found = None
                for selector in img_selectors:
                    img_elements = article_soup.select(selector)
                    if img_elements:
                        # 通常第一個圖片是我們需要的
                        img_found = img_elements[0].get('src')
                        if img_found:
                            break

                # 如果以上選擇器都沒找到，嘗試尋找任何圖片
                if not img_found:
                    all_imgs = article_soup.select('img')
                    for img in all_imgs:
                        src = img.get('src')
                        if src and ('blogspot.com' in src or 'jetsoclub.com' in src or 'bp.blogspot.com' in src):
                            img_found = src
                            break

                if img_found:
                    # 構建JSON對象
                    result_obj = {
                        "category": "", # 類型
                        "contact": "", # 聯絡方式
                        "desc1": "",    #消費劵條款
                        "desc2": img_found, #地址或網址
                        "expireDate": expire_date, # 下架日期
                        "img": img_found, #圖片網址
                        "owner": "", #消費劵店主
                        "regions": "", #店舖地區
                        "title": article['title'] #公司名稱或標題
                    }
                    results.append(result_obj)
                    print(f"找到圖片: {img_found}")
                else:
                    print("未找到圖片")

                # 添加隨機延遲，避免請求過於頻繁
                time.sleep(random.uniform(1, 3))

            except Exception as e:
                print(f"處理文章時出錯: {article['url']}, 錯誤: {str(e)}")
                continue

        # 輸出JSON格式的結果
        print("\njson = ")
        print(json.dumps(results, ensure_ascii=False, indent=2))

        # 將結果保存到文件
        if results:
            return results
        else:
            print("未找到任何結果")
            return []

    except Exception as e:
        print(f"爬蟲執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return []














#up料
# 更新batch_import函数，确保regions字段为包含"全香港"的字符串数组
def batch_import(data_list, 集合名):
    # 初始化Firebase应用
    cred = credentials.Certificate(firebase_key)  # 替换为你的K路径
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)

    # 获取Firestore客户端
    db = firestore.client()

    print(f"准备导入 {len(data_list)} 条需求到 {集合名}/main 的 ads 数组...")

    # 处理每条数据，确保regions字段格式正确
    processed_data = []
    for item in data_list:
        # 确保regions是字符串数组，且包含"全香港"作为第一个元素
        regions = item.get('regions', [])

        # 如果regions不是列表，创建新列表
        if not isinstance(regions, list):
            regions = []

        # 确保"全香港"是第一个元素
        if "全香港" not in regions:
            regions.insert(0, "全香港")
        else:
            # 如果已存在，移到第一个位置
            regions.remove("全香港")
            regions.insert(0, "全香港")

        # 确保数组中所有元素都是字符串
        regions = [str(region) for region in regions]

        # 更新当前项的regions字段
        item['regions'] = regions
        processed_data.append(item)

    # 获取main文档引用
    doc_ref = db.collection(集合名).document("main")

    # 读取现有文档（如果不存在会自动创建）
    doc = doc_ref.get()
    existing_data = doc.to_dict() if doc.exists else {}

    # 确保ads数组存在
    existing_ads = existing_data.get("ads", [])

    # 添加新数据到数组
    existing_ads.extend(processed_data)

    # 保存更新后的数据
    doc_ref.set({
        "ads": existing_ads
    })

    print(f"已成功导入 {len(processed_data)} 条需求，当前ads数组总长度: {len(existing_ads)}")
    return len(processed_data)











# 修改后的update_last_modified_date函数：更新或创建ads集合的updata文档
def update_last_modified_date(集合名, 文檔ID):
    # 初始化Firebase应用
    cred = credentials.Certificate(firebase_key)  # 替换为你的K路径
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)

    # 获取当前日期
    今日日期 = datetime.now().strftime('%Y-%m-%d')

    # 操作指定文档（不存在会自动创建）
    db = firestore.client()
    doc_ref = db.collection(集合名).document(文檔ID)

    # 使用set方法，不存在则创建，存在则更新
    doc_ref.set({
        '更新日期': 今日日期
    }, merge=True)  # merge=True确保只更新指定字段，不覆盖其他字段

    print(f"已更新/创建 {集合名}/{文檔ID} 的更新日期为: {今日日期}")
    return 今日日期














if __name__ == "__main__":

    url = 'https://www.jetsoclub.com/'


    # 检查是否今天已经更新过
    if check_if_updated_today('ads', 'updata'):
        print("今天已经更新过数据，不执行操作")
    else:
        料 = jetsoclub_crawler(url)

        if 料:
            導入數量 = batch_import(料, 'ads')
            # 更新日期
            今日 = update_last_modified_date('ads', 'updata')
            print(f"成功導入 {導入數量} 條需求, 更新日期 = {今日}")
        else:
            print("未獲取到任何需求，未進行導入操作")