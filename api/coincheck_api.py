import logger
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
import ccxt
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

        self.connection_error_count = 0

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
    def coin_get_balance(self):
        #order_type : market_sell : 成行注文　現物取引　売り
        nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100

 

        c = self.ccPrivateApi("/api/accounts/balance",nonce)
        r = c.json()

        if r['success'] != True:
            error_message = r['error']
            msg = str(datetime.datetime.now()) + ',ccerror,'+ str(error_message) + '\n'
            log.error(msg)
            #log_output(trade_log_path,msg)
        return r

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
        c = self.ccPrivateApi("/api/exchange/orders",nonce,
                            {"pair":"btc_jpy",
                            "order_type":"market_sell",
                            "amount":btc})
        r = c.json()

        if r['success'] != True:
            error_message = r['error']
            msg = str(datetime.datetime.now()) + ',ccerror,'+ str(error_message) + '\n'
            log.error(msg)
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
        c = self.ccPrivateApi("/api/exchange/orders",nonce,
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
    def coincheck_get_board(self):

        try:
            url = 'https://coincheck.jp/api/order_books'
            result = requests.get(url).json()

        except ConnectionResetError as c:
            log.critical("Coincheck:coincheck_get_board ConnectionResetError")
            t = traceback.format_exc()
            slack.Slack.post_message(t)

            self.connection_error_count += 1
            if self.connection_error_count > 2:
                log.critical("Coincheck:coincheck_get_board ConnectionResetError count over.")
                quit()
            else:
                time.sleep(1)
                self.coincheck_get_board()

        except json.decoder.JSONDecodeError as j:
            log.critical("Coincheck:coincheck_get_board JSONDecodeError")
            t = traceback.format_exc()
            slack.Slack.post_message(t)

            self.connection_error_count += 1
            if self.connection_error_count > 2:
                log.critical("Coincheck:coincheck_get_board JSONDecodeError count over.")
                quit()
            else:
                time.sleep(1)
                self.coincheck_get_board()
        else:
            self.connection_error_count = 0
        return result

    #################################
    #板の入っている価格の枚数を取得する。
    #################################
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


    #######################################################################
    #板から指定された価格帯の枚数の合計を取得する。
    # ex: 3を指定した場合、上から、または下から３枚の板の指値の合計枚数を返却する。
    #######################################################################
    def coincheck_get_board_ask_lot_sum(self,result,board_num):
        lot = 0
        asks = result.get("asks")

        for i in range(board_num):
            lot = lot + float(asks[i][1])

        return lot

    def coincheck_get_board_bid_lot_sum(self,result,board_num):
        lot = 0
        bids = result.get("bids")

        for i in range(board_num):
            lot = lot + float(bids[i][1])

        return lot


    #指定した板のロットを取得する。
    #指定した板がboard_numberより小さい場合は、board_numberのプライスを返却する。
    #指定した板までの合計枚数が、rate倍となるような板の価格を取得する。
    def coin_get_ticker_by_size(self,board,entry_lot_size,board_number,rate):

        ask_lot_sum = 0 
        bid_lot_sum = 0
        ask = 0
        bid = 0

        if board_number < 1:
            log.error('板の価格設定が異常のため、終了します。')

        board_number = board_number - 1

        for i in range(len(board['asks'])):
            ask_lot_sum += float(board['asks'][i][1])

            if ask_lot_sum >= entry_lot_size * rate:
                if i < board_number:
                    i = board_number

                ask = board['asks'][i][0]

                log.info('coin ask 板枚数:' + str(i))
                break

        for j in range(len(board['bids'])):
            bid_lot_sum += float(board['bids'][j][1])

            if bid_lot_sum >= entry_lot_size * rate:
                if j < board_number:
                    j = board_number

                bid = board['bids'][j][0]

                log.info('coin bid 板枚数:' + str(j))
                break

        if i >= len(board['bids']) or j >= len(board['asks']):
            log.error("Error : 有効価格が取得できた板の範囲外にあります。")

        return {'bid': [bid,bid_lot_sum],'ask': [ask,ask_lot_sum]}

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
