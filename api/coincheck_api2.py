from common.logger import Logger
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
sys.path.append(str(current_dir) + '/../')

CONFIG_FILE = '../config/zaif_coincheck_config.ini'
LOG = Logger(__name__)


class CoincheckApi:

    def __init__(self):

        self.conf = configparser.ConfigParser()
        self.conf.read_file(codecs.open(CONFIG_FILE, "r", "utf8"))

        # APIキーの取得
        self.MODE = self.conf.get('env', 'mode')
        self.API_KEY = self.conf.get("api_keys", "coin_access_key")
        self.API_SECRET_KEY = self.conf.get("api_keys", "coin_secret_key")
        self.LOG_PATH = self.conf.get("path", "trade_log_path")  # ログパスの取得

        # デバッグ設定
        self.DEBUG_BALANCE_LOG = '../trade_log/debug_coincheck_balance.log'

    ###############################################
    # 残高の取得
    ###############################################
    @retry(exceptions=(Exception), tries=3, delay=5)
    def getBalance(self):
        if self.MODE == 'production':
            # order_type : market_sell : 成行注文　現物取引　売り
            nonce = self.buildNonce()

            c = self.ccPrivateApi("/api/accounts/balance", nonce)
            r = c.json()

            if r['success'] != True:
                error_message = r['error']
                msg = str(datetime.datetime.now()) + \
                    ',ccerror,' + str(error_message) + '\n'
                LOG.error(msg)

            return r
        else:
            return self.debugGetBalance()

    ###################################
    # coincheckで成行でBitcoinを買う関数
    ###################################
    def marketAsk(self, btc, ask):
        # btc分だけのBitcoinをcoincheckで買います。
        # order_type : market_buy : 成行注文　現物取引　買い
        # 買いの成行注文をする場合は、market_buy_amountを指定する必要がある。(JPY)
        # market_buy_amountは日本円で渡す必要があるため、 int(btc * coin_ask)としている。
        #nonce = int((datetime.datetime.today() - datetime.datetime(2021,2,11)).total_seconds()) * 100

        if self.MODE == 'production':
            nonce = self.buildNonce()
            c = self.ccPrivateApi("/api/exchange/orders", nonce,
                                  {
                                      "pair": "btc_jpy",
                                      "order_type": "market_buy",
                                      "market_buy_amount": int(btc*ask)
                                  }
                                  )
            r = c.json()

            if r['success'] != True:
                error_message = r['error']
                msg = str(datetime.datetime.now()) + \
                    ',ccerror,' + str(error_message) + '\n'
                LOG.error(msg)

            return r
        else:
            return self.debugMakertAsk(btc, ask)

    ###################################
    # coincheckでbtc分のBitcoinを売る関数
    ###################################
    def marketBid(self, btc, bid):

        if self.MODE == 'production':
            # order_type : market_sell : 成行注文　現物取引　売り
            nonce = self.buildNonce()

            c = self.ccPrivateApi("/api/exchange/orders", nonce,
                                  {"pair": "btc_jpy",
                                   "order_type": "market_sell",
                                   "amount": btc})
            r = c.json()

            if r['success'] != True:
                error_message = r['error']
                msg = str(datetime.datetime.now()) + \
                    ',ccerror,' + str(error_message) + '\n'
                LOG.error(msg)

            return r

        else:
            return self.debugMarketBid(btc, bid)

    #############################
    # coincheckの板情報を取得する。
    #############################
    @retry(exceptions=(Exception), tries=3, delay=5)
    def getBoard(self):
        url = 'https://coincheck.jp/api/order_books'
        result = requests.get(url).json()
        return result

    ##########################
    # 残高からjpyを取得する
    ##########################
    def getBalanceJpy(self, result):
        for item in result:
            if item['currency'] == 'JPY':
                return item['balance']

    ##########################
    # 残高からbtcを取得する
    ##########################
    def getBalanceBtc(self, result):
        for item in result:
            if item['currency'] == 'BTC':
                return item['balance']

    ##########################
    # デバッグ用残高取得メソッド
    ##########################
    def debugGetBalance(self):

        if os._exists(self.DEBUG_BALANCE_LOG) != True:
            balance_log = pathlib.Path(self.DEBUG_BALANCE_LOG)
            balance_log.touch()

        with open(self.DEBUG_BALANCE_LOG, "r") as f:
            line = f.readline()
            print(line)
            jb = json.loads(line)

        balance = [{'currency': 'JPY', 'balance': float(jb['jpy'])}, {
            'currency': 'BTC', 'balance': float('{:.3f}'.format(float(jb['btc'])))}]
        return balance

    def debugMakertAsk(self, lot, ask):
        f = open(self.DEBUG_BALANCE_LOG, "r")
        balance = json.loads(f.readline())
        f.close()

        balance['jpy'] = float(balance['jpy']) - float(lot) * float(ask)
        balance['btc'] = float(balance['btc']) + float(lot)

        f = open(self.DEBUG_BALANCE_LOG, "w")
        json.dump(balance, f)
        f.close()

        LOG.info("Coincheckの残高ログをAskで更新しました。")

    def debugMarketBid(self, lot, bid):
        f = open(self.DEBUG_BALANCE_LOG, "r")
        balance = json.loads(f.readline())
        f.close()

        balance['jpy'] = float(balance['jpy']) + float(lot) * float(bid)
        balance['btc'] = float(balance['btc']) - float(lot)

        f = open(self.DEBUG_BALANCE_LOG, "w")
        json.dump(balance, f)
        f.close()

        LOG.info("Coincheckの残高ログをBidで更新しました。")

    # --------------------------------------------------------------------------
    # API固有のメソッド
    # --------------------------------------------------------------------------

    #######################################
    # coincheckのPrivateAPIリクエスト送信関数
    #######################################
    def ccPrivateApi(self, i_path, i_nonce, i_params=None, i_method="get"):
        API_URL = "https://coincheck.com"
        headers = {'ACCESS-KEY': self.API_KEY,
                   'ACCESS-NONCE': str(i_nonce),
                   'Content-Type': 'application/json'}

        s = hmac.new(bytearray(self.API_SECRET_KEY.encode(
            'utf-8')), digestmod=hashlib.sha256)

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
    # 取引履歴の取得
    ###############################################
    @retry(exceptions=(Exception), tries=3, delay=5)
    def coin_get_transactions(self):
        #nonce = int((datetime.datetime.today() - datetime.datetime(2021,2,11)).total_seconds()) * 100
        nonce = self.buildNonce()

        c = self.ccPrivateApi("/api/exchange/orders/transactions", nonce)
        r = c.json()

        if r['success'] != True:
            error_message = r['error']
            msg = str(datetime.datetime.now()) + \
                ',ccerror,' + str(error_message) + '\n'
            LOG.error(msg)
        else:
            # brker
            LOG.tradelog(r)

        return r

    ###############################################
    # coincheckのtickerを取得する関数(publicApiを使用)
    ###############################################
    @retry(exceptions=(Exception), tries=3, delay=5)
    def coin_get_ticker(self):
        url = 'https://coincheck.jp/api/ticker'
        return requests.get(url).text

    ##############################
    # coincheckでbtcを指値で買う関数
    ##############################
    def trade_coin_ask_limit_price(self, btc, coin_ask):
        #nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100
        nonce = self.buildNonce()

        c = self.ccPrivateApi("/api/exchange/orders", nonce,
                              {"pair": "btc_jpy",
                               "order_type": "buy",
                               "rate": int(coin_ask*1.1),
                               "amount": btc})
        r = c.json()

        return r

    ##########################
    # 残高からjpyを取得する
    ##########################
    def coin_get_balance_jpy(self, result):
        return result['jpy']

    ##########################
    # 残高からbtcを取得する
    ##########################
    def coin_get_balance_btc(self, result):
        return result['btc']

    def buildNonce(self):

        #nonce = int(datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'))-int(datetime.datetime(2021,2,11,0,0,0).strftime('%Y%m%d%H%M%S%f'))
        # LOG.error(nonce)
        now = datetime.datetime.now()
        now_ts = now.timestamp()
        nonce = int(now_ts * 1000000)

        LOG.error(nonce)
        return nonce


if __name__ == "__main__":

    api = CoincheckApi()
    print(api.getBoard())
