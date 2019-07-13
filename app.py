from flask import Flask, request, abort
import configparser
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests
import random

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

app = Flask(__name__)

# 讀取相關config
config = configparser.ConfigParser()
config.read("config.ini")

# line_bot_api = LineBotApi(config['line_bot']['Channel_Access_Token'])
# handler = WebhookHandler(config['line_bot']['Channel_Secret'])
# client_id = config['imgur_api']['Client_ID']
# client_secret = config['imgur_api']['Client_Secret']
# album_id = config['imgur_api']['Album_ID']
# API_Get_Image = config['other_api']['API_Get_Image']

line_bot_api = LineBotApi(os.environ['CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['CHANNEL_SECRET'])
google_api_key = os.environ['GOOGLE_API_KEY']
line_reply_api = 'https://api.line.me/v2/bot/message/reply'


@app.route('/')
def index():
    return "<p>Flask is working!</p>"


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    # print("body:",body)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'ok'


# 爬ptt
def craw_page(res, push_rate):
    soup_ = BeautifulSoup(res.text, 'html.parser')
    article_seq = []
    for r_ent in soup_.find_all(class_="r-ent"):
        try:
            # 先得到每篇文章的篇url
            link = r_ent.find('a')['href']
            if link:
                # 確定得到url再去抓 標題 以及 推文數
                title = r_ent.find(class_="title").text.strip()
                rate = r_ent.find(class_="nrec").text
                url = 'https://www.ptt.cc' + link
                if rate:
                    rate = 100 if rate.startswith('爆') else rate
                    rate = -1 * int(rate[1]) if rate.startswith('X') else rate
                else:
                    rate = 0
                # 比對推文數
                if int(rate) >= push_rate:
                    article_seq.append({
                        'title': title,
                        'url': url,
                        'rate': rate,
                    })
        except Exception as e:
            print('本文已被刪除', e)
    return article_seq


def get_page_number(content):
    start_index = content.find('index')
    end_index = content.find('.html')
    page_number = content[start_index + 5: end_index]
    return int(page_number) + 1


def ptt_beauty():
    rs = requests.session()
    res = rs.get('https://www.ptt.cc/bbs/SNSD/index.html')
    soup = BeautifulSoup(res.text, 'html.parser')
    all_page_url = soup.select('.btn.wide')[1]['href']
    start_page = get_page_number(all_page_url)  # 歷史總頁數
    page_term = 2  # 欲查看頁數
    push_rate = 10  # 對選擇的推文做人氣限制(> 10)
    index_list = []
    article_list = []
    for page in range(start_page, start_page - page_term, -1):
        page_url = 'https://www.ptt.cc/bbs/SNSD/index{}.html'.format(page)
        index_list.append(page_url)

    # 抓取 文章標題 網址 推文數
    while index_list:
        index = index_list.pop(0)
        res = rs.get(index)
        # 如網頁忙線中,則先將網頁加入 index_list 並休息1秒後再連接
        if res.status_code != 200:
            index_list.append(index)
            # time.sleep(1)
        else:
            article_list = craw_page(res, push_rate)
            # time.sleep(0.05)
    content = ''
    for article in article_list:
        data = '[{} push] {}\n{}\n\n'.format(article.get('rate', None), article.get('title', None),
                                             article.get('url', None))
        content += data
    return content


# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 使用者輸入的文字
    msg = event.message.text
    # 使用者的id
    uid = event.source.user_id

    # 如果問的跟餐廳有關
    if "餐廳" in msg:
        buttons_template_message = TemplateSendMessage(
            alt_text="Please tell me where you are",
            template=ButtonsTemplate(
                text="Please tell me where you are",
                actions=[
                    # 傳送目前位置
                    URITemplateAction(
                        label="Send my location",
                        uri="line://nv/location"
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template_message)
        return 0

    # 畫圖app
    if "畫圖" in msg or "draw" in msg:
        draw_message = TemplateSendMessage(
            alt_text="點擊下方連結開始畫圖",
            template=ButtonsTemplate(
                text="點擊下方連結開始畫圖",
                actions=[
                    URITemplateAction(
                        label="開始畫圖",
                        uri="line://app/1593667175-GOwYBOBO"
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, draw_message)
        return 0

    # 用request將訊息POST回去
    if "測試" in msg:
        # 設定header
        reply_header = {'Content-Type': 'application/json; charset=UTF-8',
                        'Authorization': 'Bearer ' + os.environ['CHANNEL_ACCESS_TOKEN'], }
        # 設定回傳的訊息格式
        reply_json = {
            "replyToken": event.reply_token,
            "messages": [{
                "type": "flex",
                "altText": "Flex Message",
                "contents": {
                    "type": "bubble",
                    "direction": "ltr",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "Header",
                                "align": "center"
                            }
                        ]
                    },
                    "hero": {
                        "type": "image",
                        "url": "https://developers.line.me/assets/images/services/bot-designer-icon.png",
                        "size": "full",
                        "aspectRatio": "1.51:1",
                        "aspectMode": "fit"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "Body",
                                "align": "center"
                            }
                        ]
                    },
                    "footer": {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "button",
                                "action": {
                                    "type": "uri",
                                    "label": "Button",
                                    "uri": "https://linecorp.com"
                                }
                            }
                        ]
                    }
                }
            }]
        }
        res = requests.post(line_reply_api, headers=reply_header, json=reply_json)

    # 用line_bot_api將客製化的訊息返回
    if "SNSD" in msg:
        uri_message = TemplateSendMessage(
            alt_text="영원히소녀시대！",
            template=ButtonsTemplate(
                text="영원히소녀시대！",
                actions=[
                    URIAction(
                        label="SNSD PTT page",
                        uri="https://www.ptt.cc/bbs/SNSD/index.html"
                    )
                ]
            )
        )

        line_bot_api.reply_message(event.reply_token, uri_message)
        return 0

    # 找PTT熱門文章
    if "PTT" in msg:
        content = ptt_beauty()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=content))
        return 0

    # 詢問空氣品質 (政府API)
    if "空氣" in msg or "PM2.5" in msg:
        gov_api = 'http://opendata.epa.gov.tw/api/v1/AQI?%24skip=0&%24top=10&%24format=json'
        response = requests.get(gov_api)
        air_data = response.json()
        msg_text1 = air_data[0]['SiteName'] + '空氣品質: ' + air_data[0]['Status']
        msg_text2 = 'PM2.5 = ' + air_data[0]['PM2.5']
        # 可以一次回傳多筆訊息(最多五筆)
        line_bot_api.reply_message(event.reply_token,
                                   [TextSendMessage(text=msg_text1), TextSendMessage(text=msg_text2)])
        return 0

    # 回傳貼圖
    if "貼圖" in msg or "sticker" in msg:
        # 回傳隨機貼圖
        sticker_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 21, 100, 101, 102, 103, 104, 105,
                       106,
                       107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124,
                       125,
                       126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 401, 402]
        index_id = random.randint(0, len(sticker_ids) - 1)
        sticker_id = str(sticker_ids[index_id])
        message = StickerSendMessage(
            package_id='1',
            sticker_id=sticker_id
        )
        line_bot_api.reply_message(event.reply_token, message)

    # 處理postback的text
    if "postback" in msg:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='觸發postback文字'))

    # 詢問是否滿意服務
    if "服務" in msg:
        confirm_message = TemplateSendMessage(
            alt_text='Confirm template',
            template=ConfirmTemplate(
                text='對於此Bot的服務滿意嗎?',
                actions=[
                    # 左右的回答可以用不同型態的template
                    PostbackTemplateAction(
                        label='Yes',
                        # 可以設為None (如果有填值只會觸發text, 且使用者會輸入該text)
                        # text=None,
                        # 會直接回傳到bot
                        data='like_service'
                    ),
                    MessageTemplateAction(
                        # 顯示在選項中的文字
                        label='No',
                        # 點擊該選項後，會發送出的文字訊息
                        text='text'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, confirm_message)

    # 輪播示範
    if "目錄" in msg or "功能" in msg or "menu" in msg:
        menu_template_message = TemplateSendMessage(
            alt_text='目錄 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://yellowslugreviews.files.wordpress.com/2015/07/2015070710112851253.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            MessageAction(
                                label='開始玩',
                                text='開始玩'
                            ),
                            URIAction(
                                label='Line Bot教學網頁',
                                uri='https://chat-bot.johnny12150.site'
                            ),
                            URIAction(
                                label='Line Bot 開源碼',
                                uri='https://github.com/johnny12150/line-bot-flask'
                            )
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/pSesLE2.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            MessageAction(
                                label='找餐廳',
                                text='找餐廳'
                            ),
                            MessageAction(
                                label='空氣品質查詢',
                                text='空氣品質查詢'
                            ),
                            URIAction(
                                label='聯絡作者',
                                uri='https://www.facebook.com/johnny12150'
                            )
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/r7UUilc.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            URIAction(
                                label='Line Bot教學投影片',
                                uri='https://1drv.ms/p/s!Aigohf1HXs8Uj1ePAuzEqNVSKRqe'
                            ),
                            URIAction(
                                label='畫圖',
                                uri='line://app/1593667175-GOwYBOBO'
                            ),
                            MessageAction(
                                label='服務滿意度調查',
                                text='服務滿意度'
                            )
                        ]
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, menu_template_message)

    if "訂餐" in msg or "外送" in msg or 'eats' in msg or 'panda' in msg:
        message = TemplateSendMessage(
            alt_text='請選擇訂餐平台',
            template=ButtonsTemplate(
                thumbnail_image_url='https://storage.googleapis.com/ubereats/UE-FB-Post.png',
                title='訂餐平台',
                text='請選擇訂餐平台',
                actions=[
                    PostbackAction(
                        label='UberEats',
                        data='UberEats'
                    ),
                    PostbackAction(
                        label='FoodPandas',
                        data='FoodPandas'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, message)

    # 如果前面條件都沒觸發，回應使用者輸入的話
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))


# 處理位置訊息
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    # 獲取使用者的經緯度
    lat = event.message.latitude
    long = event.message.longitude
    # 使用google API搜尋附近的餐廳
    nearby_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?key={}&location={},{}&rankby=distance&type=restaurant&language=zh-TW".format(
        google_api_key, lat, long)
    # 得到附近的20家餐廳資訊
    nearby_results = requests.get(nearby_url)
    nearby_restaurants_dict = nearby_results.json()
    top20_restaurants = nearby_restaurants_dict["results"]
    # 選擇評價>4分的餐聽
    res_num = (len(top20_restaurants))
    above4 = []
    for i in range(res_num):
        try:
            if top20_restaurants[i]['rating'] > 3.9:
                # print('rate: ', top20_restaurants[i]['rating'])
                above4.append(i)
        except:
            KeyError

    if len(above4) < 0:
        print('no 4 start resturant found')
        # 隨機選擇一間餐廳
        restaurant = random.choice(top20_restaurants)
    restaurant = top20_restaurants[random.choice(above4)]
    # 4. 檢查餐廳有沒有照片，有的話會顯示
    if restaurant.get("photos") is None:
        thumbnail_image_url = None
    else:
        # 根據文件，選一張照片
        photo_reference = restaurant["photos"][0]["photo_reference"]
        thumbnail_image_url = "https://maps.googleapis.com/maps/api/place/photo?key={}&photoreference={}&maxwidth=1024".format(
            google_api_key, photo_reference)
    # 餐廳詳細資訊
    rating = "無" if restaurant.get("rating") is None else restaurant["rating"]
    address = "沒有資料" if restaurant.get("vicinity") is None else restaurant["vicinity"]
    details = "評分：{}\n地址：{}".format(rating, address)

    # 取得餐廳的 Google map 網址
    map_url = "https://www.google.com/maps/search/?api=1&query={lat},{long}&query_place_id={place_id}".format(
        lat=restaurant["geometry"]["location"]["lat"],
        long=restaurant["geometry"]["location"]["lng"],
        place_id=restaurant["place_id"]
    )

    # 回覆使用 Buttons Template
    buttons_template_message = TemplateSendMessage(
        alt_text=restaurant["name"],
        template=ButtonsTemplate(
            thumbnail_image_url=thumbnail_image_url,
            title=restaurant["name"],
            text=details,
            actions=[
                # 同URIAction
                URITemplateAction(
                    label='查看地圖',
                    uri=map_url
                ),
            ]
        )
    )
    line_bot_api.reply_message(
        event.reply_token,
        buttons_template_message)


# 爬ubereats有哪些餐廳
def craw_ubereats(link):
    restaurant_list = []
    options = Options()
    options.binary_location = os.environ.get('GOOGLE_CHROME_BIN')
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--remote-debugging-port=9222')
    web = webdriver.Chrome(executable_path=str(os.environ.get('CHROMEDRIVER_PATH')), options=options)
    web.get(link)
    soup = BeautifulSoup(web.page_source, 'xml')
    for name in soup.find_all('a'):
        # 取餐廳url
        if 'food-delivery' in name['href']:
            # restaurant_list.append(name['href'])
            # 取url中餐廳名的部分(被url encode過)
            # name['href'].split('food-delivery/')[1].split('/')[0]
            # decode方式 urllib.parse.unquote()
            try:
                # 取餐廳名稱
                restaurant_list.append(name.div.figure.find_next_siblings('div')[0].div.get_text())
            except:
                continue

    web.close()
    return restaurant_list


# 處理按下按鈕後的postback
@handler.add(PostbackEvent)
def handle_postback(event):
    # 注意!! 這裡的event.message是取不到text的
    data = event.postback.data

    if data == "like_service":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='感謝您喜歡我們的服務!!'))

    if "UberEats" in data:
        # 送餐地址
        location = 'https://www.ubereats.com/zh-TW/feed/?pl=JTdCJTIyYWRkcmVzcyUyMiUzQSUyMiVFNSU5QyU4QiVFNyVBQiU4QiVFNCVCQSVBNCVFOSU4MCU5QSVFNSVBNCVBNyVFNSVBRCVCOCVFNSU4NSU4OSVFNSVCRSVBOSVFNiVBMCVBMSVFNSU4RCU4MCUyMiUyQyUyMnJlZmVyZW5jZSUyMiUzQSUyMkNoSUpNVjhrNzFjMmFEUVJtajV5T25fYUtUayUyMiUyQyUyMnJlZmVyZW5jZVR5cGUlMjIlM0ElMjJnb29nbGVfcGxhY2VzJTIyJTJDJTIybGF0aXR1ZGUlMjIlM0EyNC43ODk0MjY0OTk5OTk5OTglMkMlMjJsb25naXR1ZGUlMjIlM0ExMjEuMDAwMTIwNyU3RA%3D%3D'
        # 透過爬蟲抓出交大可以訂的餐廳
        restaurants = craw_ubereats(location)

        # 回傳交大可以訂的餐廳
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='\n'.join(restaurants[:5])))

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text='postback被觸發'))


# 執行flask
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
