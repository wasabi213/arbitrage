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
import jwt
from retry import retry

import pathlib
current_dir = pathlib.Path(__file__).resolve().parent
sys.path.append( str(current_dir) + '/../' )
from common.logger import Logger

CONFIG_FILE = '../config/arbitrage_config.ini'
log = Logger(__name__)

class LiquidApi:

    def __init__(self):

        self.conf = configparser.ConfigParser()
        self.conf.read_file(codecs.open(CONFIG_FILE,"r","utf8"))

        #APIキーの取得
        self.MODE = self.conf.get('env','mode')
        self.API_KEY = self.conf.get("api_keys","liquid_access_key")
        self.API_SECRET_KEY = self.conf.get("api_keys","liquid_secret_key")
        self.LOG_PATH = self.conf.get("path","trade_log_path")  #ログパスの取得

        #デバッグ設定
        self.DEBUG_BALANCE_LOG = '../trade_log/debug_liquid_balance.log'

    #--------------------------------------------------------------------------
    #スーパークラスにAbstract定義するメソッド
    #--------------------------------------------------------------------------
    ##################################
    # 全資産残高の取得
    ##################################
    @retry(exceptions=(Exception),tries=3,delay=5)
    def getBalance(self):
        #self.MODE = 'production'
        if self.MODE == 'production':
            path = '/accounts/balance'
            balance = self.apiGet(path)

            print(balance)

            return balance
        
        #戻り値のフォーマットをそろえる。
        else:
            return self.debugGetBalance()

    #######################################
    #Liquid 成行買い注文
    #######################################
    def marketAsk(self,lot,ask=0):
        if self.MODE == 'production':
            result = self.marketOder(lot,'buy')
            return result
        else:
            return self.debugMakertAsk(lot,ask)

    #######################################
    #Liquid 成行売り注文
    #######################################
    def marketBid(self,lot,bid=0):
        if self.MODE == 'production':
            result = self.marketOder(lot,'sell')
            return result
        else:
            return self.debugMarketBid(lot,bid)

    #############################
    #板情報を取得する。
    #############################
    @retry(exceptions=(Exception),tries=3,delay=5)
    def getBoard(self,id=5):
        url = 'https://api.liquid.com/products/' + str(id) + '/price_levels'
        result = requests.get(url).json()
        board = {"asks":result['buy_price_levels'],"bids":result['sell_price_levels'] }

        return board

    ##########################
    #残高からjpyを取得する
    ##########################
    def getBalanceJpy(self,result):
        for row in result:
            if row['currency'] == 'JPY':
                return float(row['balance'])
        return 0

    ##########################
    #残高からbtcを取得する
    ##########################
    def getBalanceBtc(self,result):
        for row in result:
            if row['currency'] == 'BTC':
                return float(row['balance'])
        return 0

    def debugGetBalance(self):

        if os._exists(self.DEBUG_BALANCE_LOG) != True:
            balance_log = pathlib.Path(self.DEBUG_BALANCE_LOG)
            balance_log.touch()

        with open(self.DEBUG_BALANCE_LOG,"r") as f:
            line = f.readline()
            print(line)
            jb = json.loads(line)
 
        balance = [{'currency': 'JPY','balance': float(jb['jpy'])},{'currency': 'BTC', 'balance': float('{:.3f}'.format(float(jb['btc']))) }]
        return balance

    def debugMakertAsk(self,lot,ask):
       
        f = open(self.DEBUG_BALANCE_LOG,"r")
        balance = json.loads(f.readline())
        f.close()

        balance['jpy'] = float(balance['jpy']) - float(lot) * float(ask)
        balance['btc'] = float(balance['btc']) + float(lot)

        f = open(self.DEBUG_BALANCE_LOG,"w")
        json.dump(balance,f)
        f.close()

        log.info("Liquidの残高ログをAskで更新しました。")

    def debugMarketBid(self,lot,bid):
        f = open(self.DEBUG_BALANCE_LOG,"r")
        balance = json.loads(f.readline())
        f.close()

        balance['jpy'] = float(balance['jpy']) + float(lot) * float(bid)
        balance['btc'] = float(balance['btc']) - float(lot)

        f = open(self.DEBUG_BALANCE_LOG,"w")
        json.dump(balance,f)
        f.close()

        log.info("Liquidの残高ログをBidで更新しました。")

    #------------------------------------------------------------------------
    #API固有のメソッド
    #--------------------------------------------------------------------------
    #############################################
    # 認証APIの実行(GET系API用)
    #############################################
    def apiGet(self,path):

        token = self.API_KEY
        secret = self.API_SECRET_KEY
        
        url = 'https://api.liquid.com' + path
        timestamp = datetime.datetime.now().timestamp()

        payload = {
                    "path": path,
                    "nonce": timestamp,
                    "token_id": token
                  }

        signature = jwt.encode(payload, secret, algorithm='HS256')

        headers = {
                    'X-Quoine-API-Version': '2',
                    'X-Quoine-Auth': signature,
                    'Content-Type' : 'application/json'
                  }

        res = requests.get(url,headers=headers)
        return json.loads(res.text)

    #############################################
    # 認証APIの実行(POST系API用)
    #############################################
    def apiPost(self,path,query,data):

        token = self.API_KEY
        secret = self.API_SECRET_KEY
        
        url = 'https://api.liquid.com' + path + query
        timestamp = datetime.datetime.now().timestamp()

        payload = {
                    "path": path + query,
                    "nonce": timestamp,
                    "token_id": token
                }

        signature = jwt.encode(payload, secret, algorithm='HS256')

        headers = {
                    'X-Quoine-API-Version': '2',
                    'X-Quoine-Auth': signature,
                    'Content-Type' : 'application/json'
                    }

        json_data = json.dumps(data)
        res = requests.post(url,headers=headers,data=json_data)
        datas = json.loads(res.text)
        return datas

    #######################################
    #Liquid 成行注文
    #######################################
    def marketOder(self,lot,side):

        path = '/orders'
        query = ''
        product_id = 5
        quantity = lot

        data = {
                    "order": {
                        "order_type": "market",
                        "product_id": product_id,
                        "side": side,
                        "quantity": lot
                    }
                }
    
        result = self.authenticatedApi(path,query,data)
        self.get_transaction(product_id)

        return result

    ###############################################
    #取引履歴の取得
    ###############################################
    @retry(exceptions=(Exception),tries=3,delay=5)
    def get_transaction(self,id=5):

        path = '/executions/me'
        query = ''
        data = {'product_id':id}
        transaction = self.authenticatedApi(path,query,data)
        log.tradelog(transaction)

        return transaction


    @staticmethod
    def __debug_get_balance():
        debug_balance_file = self.DEBUG_BALANCE_LOG
        with open(debug_balance_file,"r") as f:
            line = f.readline()
            jb = json.loads(line)
            
        balance = { 'primary_jpy':float(jb['primary_jpy']),
                    'primary_btc':float('{:.3f}'.format(float(jb['primary_btc']))),
                    'secondary_jpy':float(jb['sefondary_jpy']),
                    'secondary_btc':float('{:.3f}'.format(float(jb['secondary_btc'])))
                    }

        return balance


if __name__ == "__main__":

    api = LiquidApi()
    print(api.getBoard())
