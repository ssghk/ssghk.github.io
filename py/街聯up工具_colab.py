# -*- coding: utf-8 -*-
"""
Google Colab Telegram Bot - 圖片轉視頻 + Instagram Reels 下載
安裝所需依賴
"""

!pip install pyTelegramBotAPI opencv-python pillow moviepy
!pip install instagrapi requests
!pip install firebase-admin


import telebot
import cv2
import numpy as np
import os
import tempfile
from PIL import Image
import io
import time
from moviepy.editor import ImageSequenceClip
import threading

from instagrapi import Client
import requests
import random

from google.colab import userdata

import json

# Firebase 相關導入
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# === 配置部分 ===
# 在這裡輸入你的Telegram Bot Token
BOT_TOKEN = userdata.get('TG找老闆api')

# Instagram 賬號配置
INSTAGRAM_USERNAME = userdata.get('igAC')
INSTAGRAM_PASSWORD = userdata.get('igPW')
 # 取出 Secrets 裡的字串 # 用 Session File / 長效登入
session_raw = userdata.get('ig_session') 

# Firebase 配置
firebase_key_str = userdata.get('k.json')
firebase_key = json.loads(firebase_key_str)

# 初始化bot
bot = telebot.TeleBot(BOT_TOKEN)

# 初始化 Firebase
try:
    firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred)


# 存儲用戶數據的字典
user_data = {}

class UserSession:
    def __init__(self):
        self.images = [] # 存儲 圖片
        self.waiting_for_images = False
        self.ig_urls = []  # 存儲 Instagram 網址
        self.waiting_for_ig_urls = False

        self.waiting_for_up_content = False  # 新增：等待用戶輸入上傳內容
        self.up_content = []  # 新增：存儲用戶要上傳的內容

        self.last_activity = time.time()























'''
  :::::::::::       ::::::::                       :::::::::       ::::::::   :::::::::::
     :+:          :+:    :+:                      :+:    :+:     :+:    :+:      :+:
    +:+          +:+                             +:+    +:+     +:+    +:+      +:+
   +#+          :#:                             +#++:++#+      +#+    +:+      +#+
  +#+          +#+   +#+#                      +#+    +#+     +#+    +#+      +#+
 #+#          #+#    #+#                      #+#    #+#     #+#    #+#      #+#
###           ########       ##########      #########       ########       ###
'''


def cleanup_old_sessions():
    """清理超過10分鐘不活動的會話"""
    current_time = time.time()
    expired_users = []
    for user_id, session in user_data.items():
        if current_time - session.last_activity > 600:  # 10分鐘
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del user_data[user_id]

def get_user_session(user_id):
    """獲取或創建用戶會話"""
    if user_id not in user_data:
        user_data[user_id] = UserSession()
    user_data[user_id].last_activity = time.time()
    return user_data[user_id]

@bot.message_handler(commands=['?', 'help'])
def send_welcome(message):
    user_session = get_user_session(message.from_user.id)
    user_session.waiting_for_images = True
    user_session.images.clear()
    
    welcome_text = """
🤖 歡迎使用街聯up工具_colab機器人！

1.生成視頻===
📸 請發送3-10張圖片給我
⏱️ 我將把它們合成為一個10秒的直向視頻

2. 輸入 /ig 執行提取 Instagram 功能 ===(被ig限制,不能用)
🔗 然後發送一個或多個 Instagram 網址
💾 我會下載視頻和提取文字內容

3. 輸入 /up 執行消費券上架功能 ===
📋 然後發送要上架的內容（支持多行）
💾 消費券將上架到街坊聯盟
"""
    bot.reply_to(message, welcome_text)



@bot.message_handler(commands=['img'])
def create_video(message):
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    if len(user_session.images) < 3:
        bot.reply_to(message, "❌ 需要至少3張圖片才能生成視頻。請先發送更多圖片。")
        return
    
    if len(user_session.images) > 10:
        bot.reply_to(message, "⚠️ 圖片數量超過10張，將使用前10張圖片。")
        user_session.images = user_session.images[:10]
    
    bot.reply_to(message, "🔄 開始處理視頻，請稍候...")
    
    try:
        # 創建臨時目錄
        with tempfile.TemporaryDirectory() as temp_dir:
            # 統一圖片尺寸為直向 720x1280
            target_size = (720, 1280)  # 直向尺寸 (寬x高)
            
            # 保存圖片到臨時文件並統一尺寸
            image_paths = []
            for i, img_data in enumerate(user_session.images):
                # 調整圖片尺寸
                img_resized = resize_image_to_target(img_data, target_size)
                
                img_path = os.path.join(temp_dir, f'image_{i}.jpg')
                cv2.imwrite(img_path, img_resized)
                image_paths.append(img_path)
            
            # 創建視頻
            video_path = os.path.join(temp_dir, 'output_video.mp4')
            create_video_from_images(image_paths, video_path, duration=10)
            
            # 發送視頻
            with open(video_path, 'rb') as video_file:
                bot.send_video(user_id, video_file, caption="🎬 您的10秒直向視頻已生成！")
            
            bot.send_message(user_id, "✅ 視頻生成完成！")
            
            # 清空用戶圖片數據
            user_session.images.clear()
            user_session.waiting_for_images = False
            
    except Exception as e:
        bot.reply_to(message, f"❌ 視頻生成失敗：{str(e)}")
        print(f"Error: {e}")





@bot.message_handler(commands=['up'])
def start_up_content(message):
    """開始數據導入流程"""
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    user_session.waiting_for_up_content = True
    user_session.up_content = []
    
    help_text = """
📝 *數據導入模式已啟動*

請發送多行內容，每行對應一個字段：

*格式說明：*
第1行: 公司名稱或標題 (必要)
第2行: 圖片網址 (必要)
第3行: 類型
第4行: 聯絡方式 
第5行: 消費劵條款
第6行: 地址或網址
第7行: 下架日期
第8行: 消費劵店主id
第9行: 店舖地區


*示例：*
街坊聯盟食飯公司
https://example.com/image.jpg
課程
98672794
食滿$100減$20
大埔廣場10號
2025-10-02
109EjNOTmkh2CRuLghiIuwTDzl02
大埔




💡 *提示：*
- 必需要所有內容（沒有內容的寫空行）
- 輸入 /go_up 結束並開始導入
- 輸入 /cancel 取消操作

所有地區:
'網店','中西區','灣仔區','東區','南區','油尖旺區','深水埗區','九龍城區','黃大仙區','觀塘區','葵青區','荃灣區','屯門區','元朗區','北區','大埔區','沙田區','西貢區','離島區'

"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['go_up'])
def process_up_content(message):
    """處理收集的數據內容"""
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    if not user_session.waiting_for_up_content:
        bot.reply_to(message, "❌ 請先使用 /up 命令開始數據導入流程")
        return
    
    if not user_session.up_content:
        bot.reply_to(message, "❌ 沒有收到任何內容")
        user_session.waiting_for_up_content = False
        return
    
    bot.reply_to(message, f"🔄 開始處理 {len(user_session.up_content)} 條內容，正在導入到數據庫...")
    
    try:
        # 構建數據列表
        data_list = []
        
        for content in user_session.up_content:
            # 分割每行內容
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            if lines:  # 確保有內容
                data_item = parse_content_to_data(lines)
                if data_item:
                    data_list.append(data_item)
        
        if not data_list:
            bot.reply_to(message, "❌ 沒有有效的可導入內容")
            return
        
        if len(data_list) != 1:
            bot.reply_to(message, f"❌ 每次只能導入1條完整內容，當前收到 {len(data_list)} 條")
            return
        
        # 導入到 Firebase
        imported_count = batch_import(data_list, 'ads')
        
        # 顯示導入的詳細結果
        result_text = f"""
✅ 數據導入完成！

成功導入 {imported_count} 條內容到數據庫。

*導入詳情：*
"""
        for i, data_item in enumerate(data_list):
            result_text += f"""
*記錄 {i+1}:*
- 公司名稱或標題: {data_item['title'] or '無'}
- 圖片網址: {data_item['img'] or '無'}
===
- 聯絡方式: {data_item['contact'] or '無'}
- 地址或網址: {data_item['desc2'] or '無'}
===
- 消費劵條款: {data_item['desc1'] or '無'}
- 下架日期: {data_item['expireDate'] or '無'}
===
- 類型: {data_item['category'] or '無'}
- 店舖地區: {data_item['regions'] or '無'}
===
- 消費劵店主: {data_item['owner'] or '無'}
"""
        
        bot.reply_to(message, result_text, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ 數據導入失敗：{str(e)}")
        print(f"數據導入錯誤: {e}")
    
    finally:
        # 重置用戶狀態
        user_session.waiting_for_up_content = False
        user_session.up_content = []







@bot.message_handler(commands=['ig'])
def start_instagram_download(message):
    """開始 Instagram Reels 下載流程"""
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    user_session.waiting_for_ig_urls = True
    user_session.ig_urls = []
    
    help_text = """
📥 Instagram Reels 下載模式已啟動

請發送 Instagram Reels 網址：
• 可以一次發送多個網址（每行一個）
• 或者分多次發送單個網址
• 輸入 /go 結束並開始下載
• 輸入 /cancel 取消操作

示例網址：
https://www.instagram.com/p/DOxD-5ljING/
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['go'])
def process_instagram_urls(message):
    """處理收集的 Instagram 網址"""
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    if not user_session.waiting_for_ig_urls:
        bot.reply_to(message, "❌ 請先使用 /ig 命令開始下載流程")
        return
    
    if not user_session.ig_urls:
        bot.reply_to(message, "❌ 沒有收到任何 Instagram 網址")
        user_session.waiting_for_ig_urls = False
        return
    
    bot.reply_to(message, f"🔄 開始處理 {len(user_session.ig_urls)} 個 Instagram 鏈接，請稍候...")
    
    try:
        # 創建臨時下載目錄
        temp_dir = tempfile.mkdtemp()
        
        # 下載 Instagram Reels
        results = download_instagram_reels_batch(
            INSTAGRAM_USERNAME, 
            INSTAGRAM_PASSWORD, 
            user_session.ig_urls, 
            download_folder=temp_dir
        )
        
        # 處理結果
        success_count = 0
        total_files = 0
        
        for i, result in enumerate(results):
            if result.get("success", False):
                success_count += 1
                
                # 發送文字內容
                caption_text = f"""
📝 文字內容：
{result['caption']}

👤 用戶: @{result['username']}
❤️ 點贊: {result['like_count']}
💬 評論: {result['comment_count']}
⏰ 發佈時間: {result['taken_at']}
"""
                bot.send_message(user_id, caption_text)
                
                # 發送下載的文件
                for file_path in result['downloaded_files']:
                    if file_path.endswith('.mp4'):
                        try:
                            with open(file_path, 'rb') as video_file:
                                bot.send_video(user_id, video_file, caption=f"📹 {os.path.basename(file_path)}")
                        except Exception as e:
                            bot.send_message(user_id, f"❌ 發送視頻失敗: {str(e)}")
                    elif file_path.endswith('.jpg'):
                        try:
                            with open(file_path, 'rb') as photo_file:
                                bot.send_photo(user_id, photo_file, caption=f"🖼️ {os.path.basename(file_path)}")
                        except Exception as e:
                            bot.send_message(user_id, f"❌ 發送圖片失敗: {str(e)}")
                
                total_files += len(result['downloaded_files'])
            else:
                # 發送錯誤信息
                error_text = f"""
❌ 處理失敗
網址: {result['url']}
錯誤: {result.get('error', '未知錯誤')}
"""
                bot.send_message(user_id, error_text)
        
        # 發送摘要
        summary = f"""
✅ Instagram 下載完成！
成功處理: {success_count}/{len(results)}
總下載文件: {total_files}
"""
        bot.send_message(user_id, summary)
        
    except Exception as e:
        bot.reply_to(message, f"❌ 處理過程中出錯: {str(e)}")
    
    finally:
        # 清理臨時文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass
        
        # 重置用戶狀態
        user_session.waiting_for_ig_urls = False
        user_session.ig_urls = []























@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    """取消當前操作"""
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    if user_session.waiting_for_ig_urls:
        user_session.waiting_for_ig_urls = False
        user_session.ig_urls = []
        bot.reply_to(message, "✅ Instagram 下載操作已取消")
    elif user_session.waiting_for_images:
        user_session.waiting_for_images = False
        user_session.images.clear()
        bot.reply_to(message, "✅ 圖片收集已取消")
    else:
        bot.reply_to(message, "ℹ️ 沒有需要取消的操作")

@bot.message_handler(func=lambda message: True)
# 修改文本消息處理函數，添加對數據導入內容的處理
@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    """處理文本消息"""
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    if user_session.waiting_for_up_content:
        # 處理數據導入內容
        text = message.text.strip()
        
        if text and not text.startswith('/'):
            user_session.up_content.append(text)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            reply_text = f"""
✅ 內容已接收！

收到 {len(lines)} 行內容：
"""
            for i, line in enumerate(lines):  
                reply_text += f"{i+1}. {line[:30]}{'...' if len(line) > 30 else ''}\n"
            
            #if len(lines) > 3:
            #    reply_text += f"... 還有 {len(lines) - 3} 行\n"
            
            reply_text += "\n💡 輸入 /go_up 開始導入或繼續發送更多內容"
            
            bot.reply_to(message, reply_text)
        else:
            bot.reply_to(message, "❌ 內容為空，請重新發送")
    
    elif user_session.waiting_for_ig_urls:
        # 處理 Instagram 網址
        text = message.text.strip()
        
        # 檢查是否是網址（簡單驗證）
        if text.startswith('http') and 'instagram.com' in text:
            user_session.ig_urls.append(text)
            bot.reply_to(message, f"✅ 網址已添加！當前網址數量: {len(user_session.ig_urls)}\n輸入 /go 開始下載或繼續發送更多網址")
        else:
            bot.reply_to(message, "❌ 這不是有效的 Instagram 網址，請發送正確的網址或輸入 /go 開始下載")
    











































'''
     :::    :::       :::::::::                       :::::::::           :::    :::::::::::           :::
    :+:    :+:       :+:    :+:                      :+:    :+:        :+: :+:      :+:             :+: :+:
   +:+    +:+       +:+    +:+                      +:+    +:+       +:+   +:+     +:+            +:+   +:+
  +#+    +:+       +#++:++#+                       +#+    +:+      +#++:++#++:    +#+           +#++:++#++:
 +#+    +#+       +#+                             +#+    +#+      +#+     +#+    +#+           +#+     +#+
#+#    #+#       #+#                             #+#    #+#      #+#     #+#    #+#           #+#     #+#
########        ###             ##########      #########       ###     ###    ###           ###     ###
'''

# ===============================
# 數據導入功能 - 多行對應字段版本
# ===============================

def batch_import(data_list, 集合名):
    """批量導入數據到 Firebase"""
    print(f"準備導入 {len(data_list)} 條數據到 {集合名}/main 的 ads 數組...")

    # 獲取Firestore客戶端
    db = firestore.client()

    # 處理每條數據，確保regions字段格式正確
    processed_data = []
    for item in data_list:
        # 確保regions是字符串數組，且包含"全香港"作為第一個元素
        regions = item.get('regions', [])

        # 如果regions不是列表，創建新列表
        if not isinstance(regions, list):
            regions = []

        # 確保數組中所有元素都是字符串
        regions = [str(region) for region in regions]

        # 更新當前項的regions字段
        item['regions'] = regions
        processed_data.append(item)

    # 獲取main文檔引用
    doc_ref = db.collection(集合名).document("main")

    # 讀取現有文檔（如果不存在會自動創建）
    doc = doc_ref.get()
    existing_data = doc.to_dict() if doc.exists else {}

    # 確保ads數組存在
    existing_ads = existing_data.get("ads", [])

    # 添加新數據到數組
    existing_ads.extend(processed_data)

    # 保存更新後的數據
    doc_ref.set({
        "ads": existing_ads
    })

    print(f"已成功導入 {len(processed_data)} 條數據，當前ads數組總長度: {len(existing_ads)}")
    return len(processed_data)

def parse_content_to_data(content_lines):
    """將多行內容解析為數據對象"""
    # 至少需要1行內容（desc1）
    if len(content_lines) < 2:
        return None

    # 補足到9行，用空字符串填充缺失的行
    while len(content_lines) < 9:
        content_lines.append('')

    店舖地區 = []
    if content_lines[8] == '':
        店舖地區 = ['全香港']
    else:
        店舖地區.insert(0, content_lines[8])
    
    # 根據行數構建數據對象
    data_item = {
        "title": content_lines[0],      # 公司名稱或標題
        "img": content_lines[1],        # 圖片網址
        "category": content_lines[2],   # 類型
        "contact": content_lines[3],    # 聯絡方式
        "desc1": content_lines[4],      # 消費劵條款
        "desc2": content_lines[5],      # 地址或網址
        "expireDate": content_lines[6], # 下架日期
        "owner": content_lines[7],      # 消費劵店主
        "regions": 店舖地區              # 店舖地區
        
    }    
    return data_item





































        

'''      :::::::::       :::      :::       :::                       :::::::::::       ::::::::
     :+:    :+:      :+:      :+:       :+:                           :+:          :+:    :+:
    +:+    +:+      +:+      +:+       +:+                           +:+          +:+
   +#+    +:+      +#+      +#+  +:+  +#+                           +#+          :#:
  +#+    +#+      +#+      +#+ +#+#+ +#+                           +#+          +#+   +#+#
 #+#    #+#      #+#       #+#+# #+#+#                            #+#          #+#    #+#
#########       ########## ###   ###         ##########      ###########       ########
'''
# ===============================
# Instagram Reels 下載功能 - 終極解決方案
# ===============================

def download_instagram_reels_batch(username, password, reel_urls, download_folder="downloads", delay=2):
    cl = Client()
    
    # 設置更真實的設備模擬
    user_agents = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ]
    
    # 設置設備參數
    cl.set_user_agent(random.choice(user_agents))
    cl.delay_range = [2, 5]  # 更長的延遲
    
    # 創建下載文件夾
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    
    # 存儲所有結果
    all_results = []
    
    try:
        # 登錄策略
        print("正在嘗試登錄 Instagram...")
        
        login_success = False
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                print(f"登錄嘗試 {attempt + 1}/{max_retries}")
                
                # 方法1: 首先嚐試使用會話
                if session_raw and attempt == 0:
                    try:
                        session_dict = json.loads(session_raw)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as f:
                            json.dump(session_dict, f)
                            temp_path = f.name
                        
                        cl.load_settings(temp_path)
                        # 嘗試不重新登錄，直接使用會話
                        cl.get_timeline_feed()  # 測試會話是否有效
                        print("✅ 會話有效，跳過登錄")
                        login_success = True
                        os.remove(temp_path)
                        break
                    except Exception as session_error:
                        print(f"會話無效: {session_error}")
                        os.remove(temp_path)
                        continue
                
                # 方法2: 嘗試直接登錄
                try:
                    print("嘗試直接登錄...")
                    cl.login(username, password, relogin=True)
                    login_success = True
                    print("✅ 直接登錄成功!")
                    break
                except Exception as login_error:
                    print(f"直接登錄失敗: {login_error}")
                    
                    # 方法3: 嘗試使用挑戰處理
                    if "challenge" in str(login_error).lower():
                        print("檢測到挑戰要求，嘗試處理...")
                        try:
                            cl.handle_challenge(username, password)
                            login_success = True
                            print("✅ 挑戰處理成功!")
                            break
                        except Exception as challenge_error:
                            print(f"挑戰處理失敗: {challenge_error}")
                    
                    # 等待後重試
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        print(f"等待 {wait_time} 秒後重試...")
                        time.sleep(wait_time)
                        
            except Exception as e:
                print(f"登錄嘗試 {attempt + 1} 失敗: {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)
        
        if not login_success:
            raise Exception("所有登錄嘗試都失敗了")
        
        print("登錄成功! 開始處理鏈接...")
        
        # 處理每個 URL
        for i, reel_url in enumerate(reel_urls):
            print(f"\n正在處理第 {i+1}/{len(reel_urls)} 個鏈接: {reel_url}")
            
            try:
                # 驗證會話狀態
                try:
                    cl.get_timeline_feed()
                except Exception as session_check_error:
                    if "login_required" in str(session_check_error).lower():
                        print("會話已過期，嘗試重新登錄...")
                        cl.login(username, password, relogin=True)
                
                # 獲取媒體信息
                media_pk = cl.media_pk_from_url(reel_url)
                
                # 更長的隨機延遲
                sleep_time = random.uniform(5, 10)
                print(f"等待 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)
                
                media_info = cl.media_info(media_pk)
                
                result = {
                    "url": reel_url,
                    "caption": media_info.caption_text if media_info.caption_text else "這個 Reels 沒有文字內容",
                    "username": media_info.user.username,
                    "like_count": media_info.like_count,
                    "comment_count": media_info.comment_count,
                    "taken_at": media_info.taken_at,
                    "downloaded_files": [],
                    "media_type": media_info.media_type,
                    "success": True
                }
                
                # 下載函數
                def download_media(url, filename):
                    try:
                        headers = {
                            'User-Agent': random.choice(user_agents),
                            'Referer': 'https://www.instagram.com/',
                            'Accept': '*/*',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Connection': 'keep-alive',
                            'Sec-Fetch-Dest': 'video',
                            'Sec-Fetch-Mode': 'no-cors',
                            'Sec-Fetch-Site': 'cross-site',
                        }
                        
                        response = requests.get(url, stream=True, headers=headers, timeout=60)
                        response.raise_for_status()
                        
                        filepath = os.path.join(download_folder, filename)
                        
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        return filepath
                    except Exception as e:
                        print(f"下載 {filename} 時出錯: {e}")
                        return None
                
                # 處理不同媒體類型
                if media_info.media_type == 2:  # 視頻
                    print("檢測到視頻內容，開始下載...")
                    # 下載視頻
                    video_url = media_info.video_url
                    if video_url:
                        filename = f"video_{int(time.time())}_{media_pk}.mp4"
                        video_path = download_media(video_url, filename)
                        if video_path:
                            result["downloaded_files"].append(video_path)
                            print(f"視頻已下載: {os.path.basename(video_path)}")
                    
                    # 下載縮略圖
                    if hasattr(media_info, 'thumbnail_url') and media_info.thumbnail_url:
                        thumbnail_filename = f"thumbnail_{int(time.time())}_{media_pk}.jpg"
                        thumbnail_path = download_media(media_info.thumbnail_url, thumbnail_filename)
                        if thumbnail_path:
                            result["downloaded_files"].append(thumbnail_path)
                
                elif media_info.media_type == 8:  # 輪播帖
                    print(f"檢測到輪播帖，包含 {len(media_info.resources)} 個媒體文件")
                    for j, resource in enumerate(media_info.resources):
                        if resource.media_type == 2:  # 視頻
                            video_url = resource.video_url
                            if video_url:
                                filename = f"video_{int(time.time())}_{media_pk}_{j+1}.mp4"
                                video_path = download_media(video_url, filename)
                                if video_path:
                                    result["downloaded_files"].append(video_path)
                                    print(f"視頻 {j+1} 已下載: {os.path.basename(video_path)}")
                
                all_results.append(result)
                
            except Exception as e:
                error_result = {
                    "url": reel_url,
                    "error": str(e),
                    "success": False
                }
                all_results.append(error_result)
                print(f"處理 {reel_url} 時出錯: {e}")
            
            # 處理間隔延遲
            if i < len(reel_urls) - 1:
                sleep_time = random.uniform(8, 15)
                print(f"處理間隔，等待 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)
        
        return all_results
            
    except Exception as e:
        error_msg = str(e)
        print(f"Instagram 處理過程中出錯: {e}")
        
        # 詳細的錯誤分類
        if "login_required" in error_msg.lower() or "user_has_logged_out" in error_msg.lower():
            detailed_error = """❌ Instagram 登錄失敗

可能原因：
1. 賬號被臨時限制
2. 需要完成安全驗證
3. IP地址被標記

解決方案：
1. 在手機上正常使用Instagram 24小時
2. 完成所有安全驗證步驟
3. 更換網絡環境
4. 等待24-48小時後重試

請使用 /ig_verify 查看詳細驗證指南"""
        elif "challenge" in error_msg.lower():
            detailed_error = """❌ Instagram 要求安全驗證

請在手機上：
1. 打開Instagram應用
2. 完成要求的驗證步驟
3. 確保可以正常瀏覽內容
4. 等待1小時後再試"""
        elif "blacklist" in error_msg.lower():
            detailed_error = "❌ IP地址被限制，請更換網絡或使用VPN"
        else:
            detailed_error = f"❌ 錯誤: {error_msg}"
        
        return [{"error": detailed_error, "success": False} for _ in reel_urls]
    finally:
        try:
            cl.logout()
            print("已安全退出")
        except:
            pass








@bot.message_handler(commands=['ig_verify'])
def manual_verification(message):
    """手動驗證 Instagram 賬號"""
    user_id = message.from_user.id
    
    verification_text = """
🔐 Instagram 賬號驗證指南

由於 Instagram 的安全限制，您需要：

1. 在瀏覽器中手動登錄 Instagram
2. 完成任何必要的驗證（郵箱/手機驗證碼）
3. 確保賬號狀態正常
4. 然後返回這裡使用 /ig 命令

如果問題持續存在：
• 嘗試更換網絡環境
• 等待幾小時後再試
• 或聯繫管理員獲取幫助
"""
    bot.send_message(user_id, verification_text)



























































































'''
      :::::::::::         :::   :::       ::::::::                   :::::::::::       ::::::::                         :::   :::       :::::::::         :::
         :+:            :+:+: :+:+:     :+:    :+:                      :+:          :+:    :+:                       :+:+: :+:+:      :+:    :+:       :+:
        +:+           +:+ +:+:+ +:+    +:+                             +:+          +:+    +:+                      +:+ +:+:+ +:+     +:+    +:+      +:+ +:+
       +#+           +#+  +:+  +#+    :#:                             +#+          +#+    +:+                      +#+  +:+  +#+     +#++:++#+      +#+  +:+
      +#+           +#+       +#+    +#+   +#+#                      +#+          +#+    +#+                      +#+       +#+     +#+           +#+#+#+#+#+
     #+#           #+#       #+#    #+#    #+#                      #+#          #+#    #+#                      #+#       #+#     #+#                 #+#
###########       ###       ###     ########       ##########      ###           ########       ##########      ###       ###     ###                 ###
'''
# ===============================
# 原有的圖片轉視頻功能
# ===============================

@bot.message_handler(commands=['status'])
def check_status(message):
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    status_text = f"""
📊 當前狀態：
📸 已接收圖片：{len(user_session.images)} 張
🔗 Instagram 網址：{len(user_session.ig_urls)} 個
⏳ 最後活動：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(user_session.last_activity))}

💡 發送 /img 生成視頻（需要至少3張圖片）
💡 發送 /ig 下載 Instagram Reels
💡 發送 /cancel 取消當前會話
"""
    bot.reply_to(message, status_text)

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    user_id = message.from_user.id
    user_session = get_user_session(user_id)
    
    if not user_session.waiting_for_images:
        bot.reply_to(message, "⚠️ 請先發送 /? 命令開始新會話。")
        return
    
    if len(user_session.images) >= 10:
        bot.reply_to(message, "⚠️ 已達到最大圖片數量（10張）。請輸入 /img 生成視頻。")
        return
    
    try:
        # 獲取最高質量的圖片
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # 轉換為OpenCV格式
        image = Image.open(io.BytesIO(downloaded_file))
        img_array = np.array(image)
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # 調整圖片尺寸（可選，保持一致性）
        img_array = resize_image(img_array, max_width=1280)
        
        user_session.images.append(img_array)
        
        bot.reply_to(message, f"✅ 圖片接收成功！當前圖片數量：{len(user_session.images)}/10\n輸入 /img 生成視頻")
        
    except Exception as e:
        bot.reply_to(message, f"❌ 圖片處理失敗：{str(e)}")

def resize_image(image, max_width=720):
    """調整圖片尺寸，保持寬高比，適合直向顯示"""
    h, w = image.shape[:2]
    
    # 對於直向視頻，我們更關心高度，但也要限制寬度
    if w > max_width:
        ratio = max_width / w
        new_width = max_width
        new_height = int(h * ratio)
        image = cv2.resize(image, (new_width, new_height))
    
    return image

def create_video_from_images(image_paths, output_path, duration=10, fps=24):
    """從圖片創建視頻"""
    # 計算每張圖片的顯示時間
    num_images = len(image_paths)
    clip_duration = duration / num_images
    
    # 創建視頻剪輯
    clip = ImageSequenceClip(image_paths, durations=[clip_duration] * num_images)
    
    # 設置幀率
    clip = clip.set_fps(fps)
    
    # 輸出視頻
    clip.write_videofile(
        output_path,
        codec='libx264',
        audio=False,
        verbose=False,
        logger=None
    )

def resize_image_to_target(image, target_size):
    """將圖片調整到目標直向尺寸，保持比例並填充黑色背景"""
    h, w = image.shape[:2]
    target_w, target_h = target_size  # 直向尺寸，例如 720x1280
    
    # 計算適合直向的縮放比例
    # 以高度為基準進行縮放，確保圖片能完整顯示在直向畫面中
    scale = target_h / h
    new_h = target_h
    new_w = int(w * scale)
    
    # 如果寬度超過目標寬度，則以寬度為基準
    if new_w > target_w:
        scale = target_w / w
        new_w = target_w
        new_h = int(h * scale)
    
    # 調整圖片尺寸
    resized = cv2.resize(image, (new_w, new_h))
    
    # 創建目標尺寸的黑色背景（直向）
    result = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    
    # 計算居中位置
    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    
    # 將調整後的圖片放在黑色背景中央
    result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
    
    return result













































'''
      ::::::::   :::::::::::           :::        :::::::::   :::::::::::
    :+:    :+:      :+:             :+: :+:      :+:    :+:      :+:
   +:+             +:+            +:+   +:+     +:+    +:+      +:+
  +#++:++#++      +#+           +#++:++#++:    +#++:++#:       +#+
        +#+      +#+           +#+     +#+    +#+    +#+      +#+
#+#    #+#      #+#           #+#     #+#    #+#    #+#      #+#
########       ###           ###     ###    ###    ###      ###
'''


def run_bot_polling():
    """運行bot輪詢"""
    print("🤖 Telegram Bot 啟動中...")
    print("📱 ⚠️ 請先發送 /? 命令開始")
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ Bot運行錯誤: {e}")
        print("🔄 嘗試重新連接...")
        time.sleep(5)
        run_bot_polling()

# === 主程序 ===
def main():
    """主函數"""
    print("=" * 50)
    print("Google Colab Telegram Bot - 圖片轉視頻 + Instagram 下載 + 數據導入")
    print("=" * 50)
    
    if BOT_TOKEN == "你的BOT_TOKEN_HERE" or not BOT_TOKEN:
        print("❌ 請先設置BOT_TOKEN！")
        print("1. 在Telegram中搜索 @BotFather")
        print("2. 創建新的bot並獲取token")
        print("3. 將token設置為userdata")
        return
    
    # 啟動會話清理線程
    def cleanup_thread():
        while True:
            time.sleep(300)  # 每5分鐘清理一次
            cleanup_old_sessions()
    
    cleanup_thread = threading.Thread(target=cleanup_thread, daemon=True)
    cleanup_thread.start()
    
    # 啟動bot
    run_bot_polling()

# 如果在Colab中運行，自動啟動
if __name__ == "__main__":
    main()