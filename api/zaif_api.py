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
from retry import retry
from common.logger import Logger
from zaifapi import ZaifPublicApi,ZaifTradeApi

CONFIG_FILE = '../config/zaif_coincheck_config.ini'
#log = logger.Logger(__name__)
log = Logger(__name__)

class ZaifApi:

    def __init__(self):

        self.conf = configparser.ConfigParser() 
        self.conf.read_file(codecs.open(CONFIG_FILE,"r","utf8"))

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

    ################################
    #残高情報を取得する。
    ################################
    @retry(exceptions=(Exception),tries=3,delay=5)
    def zaif_get_info2(self):
        zaif = ZaifTradeApi(self.API_KEY,self.API_SECRET_KEY)
        balance_info = zaif.get_info2()

        return balance_info

    ###############################
    #zaifの板情報を取得する。
    #AskとBidが反対なので入れ替える。
    ###############################
    @retry(exceptions=(Exception),tries=3,delay=5)
    def zaif_get_board(self):
        
        url = 'https://api.zaif.jp/api/1/depth/btc_jpy'
        result = requests.get(url).json()

        return result


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
