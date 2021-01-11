import datetime
import hashlib
import hmac
import requests
import json
import time
import sys
import csv
import configparser
import codecs

CONFIG_FILE = r'../config/zaif_coincheck_config.ini'

class CoincheckApi:

    def __init__(self):

        self.conf = configparser.ConfigParser()
        self.conf.readfp(codecs.open(CONFIG_FILE,"r","utf8"))

        #APIキーの取得
        self.MODE = self.conf.get('env','mode')
        self.API_KEY = self.conf.get("api_keys","coin_access_key")
        self.API_SECRET_KEY = self.conf.get("api_keys","coin_secret_key")
        self.LOG_PATH = self.conf.get("path","trade_log_path")  #ログパスの取得

    ##coincheck関係
    #######################################
    #coincheckのPrivateAPIリクエスト送信関数
    #######################################
    def ccPrivateApi(self,i_path, i_nonce, i_params=None, i_method="get"):
        API_URL = "https://coincheck.com"
        headers = {   'ACCESS-KEY':self.API_KEY, 
                    'ACCESS-NONCE':str(i_nonce), 
                    'Content-Type': 'application/json'}

        s = hmac.new(bytearray(coin_secret_key.encode('utf-8')), digestmod=hashlib.sha256)

        if i_params is None:
            w = str(i_nonce) + API_URL + i_path
            s.update(w.encode('utf-8'))
            headers['ACCESS-SIGNATURE'] = s.hexdigest()

            if i_method == "delete":
                return requests.delete(API_URL+i_path, headers=headers)
            else:
                return requests.get(API_URL+i_path, headers=headers)
        else:    
            body = json.dumps(i_params)
            w = str(i_nonce) + API_URL + i_path + body
            s.update(w.encode('utf-8'))
            headers['ACCESS-SIGNATURE'] = s.hexdigest()

        return requests.post(API_URL+i_path, data=body, headers=headers)

    ###############################################
    #coincheckのtickerを取得する関数(publicApiを使用)
    ###############################################
    def coin_get_ticker(self):
        url = 'https://coincheck.jp/api/ticker'
        return requests.get(url).text

    ###################################
    #coincheckでbtc分のBitcoinを売る関数
    ###################################
    def trade_coin_bid(self,btc):
        #order_type : market_sell : 成行注文　現物取引　売り
        nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100
        c = ccPrivateApi("/api/exchange/orders",nonce,
                            {"pair":"btc_jpy",
                            "order_type":"market_sell",
                            "amount":btc})
        r = c.json()

        if r['success'] != True:
            error_message = r['error']
            msg = str(datetime.datetime.now()) + ',ccerror,'+ str(error_message) + '\n'
            print(msg)
            log_output(trade_log_path,msg)

        return r

    ###################################
    #coincheckでbtc分のBitcoinを買う関数
    ###################################
    def trade_coin_ask(self,btc,coin_ask):
        #btc分だけのBitcoinをcoincheckで買います。
        #order_type : market_buy : 成行注文　現物取引　買い
        #買いの成行注文をする場合は、market_buy_amountを指定する必要がある。(JPY)
        #market_buy_amountは日本円で渡す必要があるため、 int(btc * coin_ask)としている。
        nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100
        c = ccPrivateApi("/api/exchange/orders",nonce,
                            {"pair":"btc_jpy",
                            "order_type":"market_buy",
                            "market_buy_amount":int(btc*coin_ask)})
        r = c.json()

        if r['success'] != True:
            error_message = r['error']
            msg = str(datetime.datetime.now()) + ',ccerror,'+ str(error_message) + '\n'
            print(msg)
            log_output(trade_log_path,msg)

        return r

    #############################
    #coincheckのいた情報を取得する。
    #############################
    def coincheck_get_board(self):
        url = 'https://coincheck.jp/api/order_books'
        result = requests.get(url).json()
        return result

    def coincheck_get_board_price(result,category,price):

        board_array = []

        if category == "asks":
            board_array = result.get("asks")
        else:
            board_array = result.get("bids")

        for board_price,lot in board_array:
            if price == board_price:
                return lot

        return 0

    #coincheckのaskを板から取得する。
    def coincheck_get_board_ask(self,result):
        asks = result.get("asks")
        return asks[0][0]

    #coincheckのbidを板から取得する。
    def coincheck_get_board_bid(self,result):
        bids = result.get("bids")
        return bids[0][0]

    def coincheck_get_board_ask_lot(self,result):
        asks = result.get("asks")
        return asks[0][1]

    #coincheckのbidを板から取得する。
    def coincheck_get_board_bid_lot(self,result):
        bids = result.get("bids")
        return bids[0][1]
