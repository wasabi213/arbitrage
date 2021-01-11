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


class ZaifApi:

    def __init__(self):

        self.conf = configparser.ConfigParser() 
        self.conf.readfp(codecs.open(CONFIG_FILE,"r","utf8"))

        #APIキーの取得
        self.MODE = self.conf.get("env","mode")
        self.API_KEY = self.conf.get("api_keys","zaif_access_key")
        self.API_SECRET_KEY = self.conf.get("api_keys","zaif_secret_key")
        self.LOG_PATH = self.conf.get("path","trade_log_path")  #ログパスの取得

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
