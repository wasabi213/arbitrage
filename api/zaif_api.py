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

from zaifapi import ZaifPublicApi,ZaifTradeApi

CONFIG_FILE = '../config/zaif_coincheck_config.ini'
log = logger.Logger(__name__)

class ZaifApi:

    def __init__(self):

        self.conf = configparser.ConfigParser() 
        self.conf.read_file(codecs.open(CONFIG_FILE,"r","utf8"))

        #APIキーの取得
        self.MODE = self.conf.get("env","mode")
        self.API_KEY = self.conf.get("api_keys","zaif_access_key")
        self.API_SECRET_KEY = self.conf.get("api_keys","zaif_secret_key")
        self.LOG_PATH = self.conf.get("path","trade_log_path")  #ログパスの取得
        #self.zaif = ZaifTradeApi(self.API_KEY,self.API_SECRET_KEY)
        #self.zaif = ZaifTradeApi('bfce8f6f-8677-43e1-9418-4be514e2ce6c','522dbe21-6925-45b6-9306-f215a25945cb')

    ##################################
    #zaifでbtc分だけのBitcoinを売る関数
    ##################################
    def trade_zaif_bid(self,btc,zaif_bid):
        zaif = ZaifTradeApi(self.API_KEY,self.API_SECRET_KEY)
        zaif.trade(currency_pair='btc_jpy',
        action = 'ask', #zaifでは「ask」が「売り」になる
        amount = btc,
        price = int((zaif_bid - 10000) / 10) * 10)

    ##################################
    #zaifでbtc分だけのBitcoinを買う関数
    ##################################
    def trade_zaif_ask(self,btc,zaif_ask):
        zaif = ZaifTradeApi(self.API_KEY,self.API_SECRET_KEY)
        zaif.trade(currency_pair='btc_jpy',
        action = 'bid', #zaifでは「bid」が「買い」になる
        amount = btc,
        price = int((zaif_ask + 10000) / 10) * 10)

    ################################
    #残高情報を取得する。
    ################################
    def zaif_get_info2(self):
        zaif = ZaifTradeApi(self.API_KEY,self.API_SECRET_KEY)
        balance_info = zaif.get_info2()
        return balance_info

    ########################
    #zaifの板情報を取得する。
    ########################
    def zaif_get_board(self):
        url = 'https://api.zaif.jp/api/1/depth/btc_jpy'
        result = requests.get(url).json()
        return result

    #########################################################
    #板情報から指定された価格に指値が入れられている枚数を取得する。
    #########################################################
    def zaif_get_board_price(self,result,category,price):
        asks = result.get("asks")
        bids = result.get("bids")

        board_array = []

        if category == "asks":
            board_array = asks
        else:
            board_array = bids

        for board_price,lot in board_array:
            if price == board_price:
                return lot

        return 0

    #板情報からaskを取得する。
    def zaif_get_board_ask(self,result):
        asks = result.get("asks")
        return asks[0][0]

    #板情報からbidを取得する。
    def zaif_get_board_bid(self,result):
        bids = result.get("bids")
        return bids[0][0]

    #板情報からaskのlotを取得する。
    def zaif_get_board_ask_lot(self,result):
        asks = result.get("asks")
        return asks[0][1]

    #板情報からbidのlotを取得する。
    def zaif_get_board_bid_lot(self,result):
        bids = result.get("bids")
        return bids[0][1]


    #######################################################################
    #板から指定された価格帯の枚数の合計を取得する。
    # ex.3を指定した場合、上から、または下から３枚の板の指値の合計枚数を返却する。
    #######################################################################
    def zaif_get_board_ask_lot_sum(self,result,board_num):
        lot = 0
        asks = result.get("asks")

        for i in range(board_num):
            lot = lot + float(asks[i][1])

        return lot

    def zaif_get_board_bid_lot_sum(self,result,board_num):
        lot = 0
        bids = result.get("bids")

        for i in range(board_num):
            lot = lot + float(bids[i][1])

        return lot

    #指定した板のロットを取得する。
    #指定した板がboard_numberより小さい場合は、board_numberのプライスを返却する。
    #指定した板までの合計枚数が、rate倍となるような板の価格を取得する。
    def zaif_get_ticker_by_size(self,board,entry_lot_size,board_number,rate):

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

                log.info('zaif ask 板枚数:' + str(i))
                break

        for j in range(len(board['bids'])):
            bid_lot_sum += float(board['bids'][j][1])

            if bid_lot_sum >= entry_lot_size * rate:
                if j < board_number:
                    j = board_number

                bid = board['bids'][j][0]

                log.info('zaif bid 板枚数:' + str(j))
                break

        if i >= len(board['bids']) or j >= len(board['asks']):
            log.error("Error : 有効価格が取得できた板の範囲外にあります。")

        return {'bid': [bid,bid_lot_sum],'ask': [ask,ask_lot_sum]}

    ##########################
    #残高からjpyを取得する
    ##########################
    def zaif_get_balance_jpy(self,result):
        return result['funds']['jpy']

    ##########################
    #残高からbtcを取得する
    ##########################
    def zaif_get_balance_btc(self,result):
        return result['funds']['btc']
