# coding:utf-8

####import設定####
import os
import pathlib
import traceback
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
from api import zaif_api,coincheck_api
from common import spreadlog,slack
from common.logger import Logger


CONFIG_FILE = '../config/zaif_coincheck_config.ini'
CONF = configparser.ConfigParser() 
CONF.read_file(codecs.open(CONFIG_FILE,"r","utf8"))
LOG_PATH = CONF.get('path','trade_log_path') 
log = Logger(__name__)


class DebugArbiTrage:

    def __init__(self):

        self.PRIMARY_BROKER   = 'liquid'
        self.SECONDARY_BROKER = 'coincheck'
        self.COMBI = self.PRIMARY_BROKER + '_' + self.SECONDARY_BROKER
        self.path = ''
        #DEBUG用残高ファイル
        self.DEBUG_BALANCE_FILE = self.path + self.COMBI + '_balance.log'

        #デバッグ用残高ファイルを作成する。
        self.createDebugBalanceLog()

    #status_logを作成する。
    def createDebugBalanceLog(self):
        #ディレクトリを取得する。
        if os.path.exists(self.DEBUG_BALANCE_FILE) == False:
            with open(self.DEBUG_BALANCE_FILE,"w") as w:
                balance = {
                            'primary_jpy': self.conf.get('debug','primary_jpy'),
                            'primary_btc': self.conf.get('debug','primary_btc'),
                            'secondary_jpy': self.conf.get('debug','secondary_jpy'),
                            'secondary_btc': self.conf.get('debug','secondary_btc'),
                          }

                json.dump(balance,w)
            log.critical("デバッグ用残高ファイルを作成しました。")

    #zaifとcoinncheckの残高を取得する。
    def getBalance(self):

        debug_balance_file = self.DEBUG_BALANCE_FILE
        with open(debug_balance_file,"r") as f:
            line = f.readline()
            jb = json.loads(line)
            
        balance = { 'primary_jpy':float(jb['primary_jpy']),
                    'primary_btc':float('{:.3f}'.format(float(jb['primary_btc']))),
                    'secondary_jpy':float(jb['sefondary_jpy']),
                    'secondary_btc':float('{:.3f}'.format(float(jb['secondary_btc'])))
                    }

        return balance


    def getBalancePrimaryJpy(self)
        balance = self.getBalance()
        return balance['primary_jpy']

    def getBalancePrimaryBtc(self)
        balance = self.getBalance()
        return balance['primary_btc']

    def getBalanceSecondaryJpy(self)
        balance = self.getBalance()
        return balance['Secondary_jpy']

    def getBalanceSecondaryBtc(self)
        balance = self.getBalance()
        return balance['Secondary_btc']

    def debugWriteBalance(self,balance):

        debug_balance_file = self.DEBUG_BALANCE_FILE

        #TESTモードでファイルへ書き込み
        with open(debug_balance_file,"w") as w:
            json.dump(balance,w)

    #Zaifで買ってCoincheckで売る。
    #def debugTradeBuyPrimaySellSecondary(self,btc_lot,primary_ask,secondary_bid):
    def debugPrimaryBuySecondarySell(self,btc_lot,primary_ask,secondary_bid):
        log.critical("#######################################")
        log.critical("##### BUY => Primary  SELL => Secondary")
        log.critical("#######################################")

        #残高バランスが崩れているときに通知する。
        balance_before = self.getBalance()

        #primaryで買った価格と数量を出力する。
        primary_jpy = float(balance_before['primary_jpy']) - (btc_lot * primary_ask)
        primary_btc = float(balance_before['primary_btc']) + btc_lot

        #secondaryで売った価格と数量を出力する。
        secondary_jpy = float(balance_before['secondary_jpy']) + (btc_lot * secondary_bid)
        secondary_btc = float(balance_before['secondary_btc']) - btc_lot

        log.critical("secondary_ask:" + str(primary_ask))
        log.critical("primary_bid:"   + str(secondary_bid))

        balance = {
                        'primary_jpy':primary_jpy,
                        'primary_btc':primary_btc,
                        'secondary_jpy':secondary_jpy,
                        'secondary_btc':secondary_btc
                    }

        self.debugWriteBalance(balance)


    #Coincheckで買ってZaifで売る。
    def debugTradeSellPrimaryBuySecondary(self,btc_lot,secondary_ask,primary_bid):
        log.critical("#######################################")
        log.critical("##### BUY => Secondary  SELL => Primary")
        log.critical("#######################################")

        balance_before = self.getBalance()
        #Secondaryで買った価格と数量を出力する。
        secondary_jpy = float(balance_before['secondary_jpy']) - (btc_lot * secondary_ask)
        secondary_btc = float(balance_before['secondary_btc']) + btc_lot

        #Primaryで売った価格と数量を出力する。
        primary_jpy = float(balance_before['primary_jpy']) + (btc_lot * primary_bid)
        primary_btc = float(balance_before['primary_btc']) - btc_lot

        log.critical("secondary_ask:" + str(secondary_ask))
        log.critical("primary_bid:" + str(primary_bid))

        balance = {
                            'primary_jpy':primary_jpy,
                            'primary_btc':primary_btc,
                            'secondary_jpy':secondary_jpy,
                            'secondary_btc':secondary_btc
                        }

        self.debugWriteBalance(balance)


if __name__ == "__main__":

