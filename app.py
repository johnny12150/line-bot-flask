from flask import Flask, request, abort
import configparser
import os
import json
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
        line_bot_api.reply_message(
            event.reply_token,
            buttons_template_message)

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

    # 如果前面條件都沒觸發，回應使用者`輸入的話
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=msg))


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


# 執行flask
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
