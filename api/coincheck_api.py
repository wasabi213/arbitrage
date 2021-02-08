#import logger
#import Logger
import datetime
import hashlib
import hmac
import requests
import json
import time
import sys
import os
import csv
import configparser
import codecs
import ccxt
from retry import retry

import pathlib
current_dir = pathlib.Path(__file__).resolve().parent
sys.path.append( str(current_dir) + '/../' )
from common.logger import Logger

CONFIG_FILE = '../config/zaif_coincheck_config.ini'
#log = logger.Logger(__name__)
log = Logger(__name__)

class CoincheckApi:

    def __init__(self):

        self.conf = configparser.ConfigParser()
        self.conf.read_file(codecs.open(CONFIG_FILE,"r","utf8"))

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

        s = hmac.new(bytearray(self.API_SECRET_KEY.encode('utf-8')), digestmod=hashlib.sha256)

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
    #残高の取得
    ###############################################
    @retry(exceptions=(Exception),tries=3,delay=5)
    def coin_get_balance(self):
        #order_type : market_sell : 成行注文　現物取引　売り
        nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100

        c = self.ccPrivateApi("/api/accounts/balance",nonce)
        r = c.json()

        if r['success'] != True:
            error_message = r['error']
            msg = str(datetime.datetime.now()) + ',ccerror,'+ str(error_message) + '\n'
            log.error(msg)

        return r

    ###############################################
    #coincheckのtickerを取得する関数(publicApiを使用)
    ###############################################
    @retry(exceptions=(Exception),tries=3,delay=5)
    def coin_get_ticker(self):
        url = 'https://coincheck.jp/api/ticker'
        return requests.get(url).text

    ###################################
    #coincheckでbtc分のBitcoinを売る関数
    ###################################
    def trade_coin_bid(self,btc):
        #order_type : market_sell : 成行注文　現物取引　売り
        nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100
        c = self.ccPrivateApi("/api/exchange/orders",nonce,
                            {"pair":"btc_jpy",
                            "order_type":"market_sell",
                            "amount":btc})
        r = c.json()

        if r['success'] != True:
            error_message = r['error']
            msg = str(datetime.datetime.now()) + ',ccerror,'+ str(error_message) + '\n'
            log.error(msg)

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
        c = self.ccPrivateApi("/api/exchange/orders",nonce,
                            {"pair":"btc_jpy",
                            "order_type":"market_buy",
                            "market_buy_amount":int(btc*coin_ask)})
        r = c.json()

        if r['success'] != True:
            error_message = r['error']
            msg = str(datetime.datetime.now()) + ',ccerror,'+ str(error_message) + '\n'
            log.error(msg)

        return r
    ##############################
    #coincheckでbtcを指値で買う関数
    ##############################
    def trade_coin_ask_limit_price(self,btc,coin_ask):
        nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100
        c = self.ccPrivateApi("/api/exchange/orders",nonce,
                            {"pair":"btc_jpy",
                            "order_type":"buy",
                            "rate":int(coin_ask*1.1),
                            "amount":btc})
        r = c.json()

        return r


    #############################
    #coincheckの板情報を取得する。
    #############################
    @retry(exceptions=(Exception),tries=3,delay=5)
    def coincheck_get_board(self):
        url = 'https://coincheck.jp/api/order_books'
        result = requests.get(url).json()
        return result


    ##########################
    #残高からjpyを取得する
    ##########################
    def coin_get_balance_jpy(self,result):
        return result['jpy']

    ##########################
    #残高からbtcを取得する
    ##########################
    def coin_get_balance_btc(self,result):
        return result['btc']


if __name__ == "__main__":

    print("Test start/")

    api = CoincheckApi()

    print(api.coin_get_balance())
    print(api.coin_get_ticker())
    print(api.trade_coin_bid(0))
    print(api.trade_coin_ask(0,0))
    print(api.trade_coin_ask_limit_price(0,0))
    print(api.coincheck_get_board())
