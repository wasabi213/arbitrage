# coding:utf-8

# ###import設定###
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
import importlib
from common import spreadlog, slack
from common.logger import Logger

from api import liquid_api,coincheck_api2

CONFIG_FILE = '../config/arbitrage_config.ini'
CONF = configparser.ConfigParser() 
CONF.read_file(codecs.open(CONFIG_FILE, "r", "utf8"))
LOG_PATH = CONF.get('path', 'trade_log_path') 
log = Logger(__name__)

# BROKER_A = 'liquid'
# BROKER_B = 'coincheck'


class BrokerArbiTrage:

    def __init__(self, broker_a, broker_b):

        self.PRIMARY_BROKER = broker_a
        self.SECONDARY_BROKER = broker_b

        # --------------------------------------------------------------------
        # 動作モード
        self.mode = CONF.get('env', 'mode')

        # 初期円残高
        self.initial_yen_amount = CONF.getint('trade','initial_yen_amount')
        # 初期BTC残高
        self.initial_btc_amount = CONF.getfloat('trade','initial_btc_amount')

        # 日本円の最小限度額
        self.minimum_yen_limit = CONF.getint('trade','minimum_yen_limit')
        # BTCの最小限度額
        self.minimum_btc_limit = CONF.getfloat('trade','minimum_btc_limit')

        # １度にエントリするBTCの枚数
        self.btc_lot = CONF.getfloat('trade','btc_lot')

        # エントリするときのスプレッド
        self.entry_spread = CONF.getint('trade','entry_spread')
        # リバースするときのスプレッド
        self.reverse_spread = CONF.getint('trade','reverse_spread')

        # 何枚目の板まで読むか。（枚数で指定）
        self.board_count = CONF.getint('trade','board_count')

        # エントリロットするに対する指値に入っているロットの倍率
        self.entry_rate = CONF.getint('trade','entry_rate')

        # スプレッドが何回連続で閾値を超えたらエントリするか。
        self.price_over_count = CONF.getint('trade','price_over_count')

        # 何秒ごとに処理を行うか。（秒）
        self.interval_second = CONF.getint('trade','interval_second')


        # スプレッドモードで動作しているか、リバースモードで動作しているか。
        self.action_mode = ''
        # primaryのスプレッドがしきい値を超えた回数
        self.primary_tradable_time = 0
        # secondarycheckのスプレッドがしきい値を超えた回数
        self.secondary_tradable_time = 0

        # 価格が変わらずに取引が成立するための十分なロット数
        self.tradable_lot = self.btc_lot * self.entry_rate

        # どちらのブローカーにBTCを戻すか。
        self.reverse_broker = ''

        # ブローカーAPIのインスタンスを保持する。
        #self.primary = self.setAPI(self.PRIMARY_BROKER)
        #self.secondary = self.setAPI(self.SECONDARY_BROKER)

        self.primary = liquid_api.LiquidApi()
        self.secondary = coincheck_api2.CoincheckApi()

        # ループ一回ごとに一度のみ取得にする。
        #self.balance = self.updateBalance()
        self.balance = {}
    

    # APIライブラリを動的にセットする。
    def setAPI(self, broker):
        api_dir = "api"
        api_files = os.listdir(api_dir)
        #current_dir = os.path.dirname(os.path.abspath(__file__))

        for api_py in api_files:
            if api_py.endswith('.py'):
                path = api_dir + "/" + api_py

                if api_py.split(".")[0] == broker:
                    cpath = os.path.splitext(path)[0].replace(os.path.sep, '.') 
                    mod = importlib.import_module(cpath)

                    return mod()

    # 最新JPY,BTCの残高を取得する。
    def updateBalance(self):

        p_balance   = self.primary.getBalance()
        primary_jpy = self.primary.getBalanceJpy(p_balance)
        primary_btc = self.primary.getBalanceBtc(p_balance)

        s_balance     = self.secondary.getBalance()
        secondary_jpy = self.secondary.getBalanceJpy(s_balance)
        secondary_btc = self.secondary.getBalanceBtc(s_balance)

        balance = {
                    'primary_jpy'  :float(primary_jpy),
                    'primary_btc'  :float(primary_btc),
                    'secondary_jpy':float(secondary_jpy),
                    'secondary_btc':float(secondary_btc)
                  }

        self.balance = balance


    def getBalance(self):
        return self.balance

    #円残高、BTC残高が十分にあるかチェックする。
    def checkBalance(self,balance):

        #状態
        if balance['primary_jpy'] + balance['secondary_jpy'] < self.initial_yen_amount:
            log.error("円残高が偏っています。")
            slack.Slack.post_message("円残高が偏っています。")

        if balance['primary_btc'] + balance['secondary_btc'] < self.initial_btc_amount:
            log.error("BTC残高が偏っています。")
            slack.Slack.post_message("円残高が偏っています。")

        if float(balance['primary_jpy']) <= float(self.minimum_yen_limit):
            log.critical(self.PRIMARY_BROKER + 'の円残高が下限に達しました。')
            direction = "reverse"
            primary_trade_type = "sell"
            secondary_trade_type = "buy"

        elif float(balance['primary_btc']) <= float(self.minimum_btc_limit):
            log.critical(self.PRIMARY_BROKER + 'のBTC残高が下限に達しました。')
            direction = "reverse"
            primary_trade_type = "buy"
            secondary_trade_type = "sell"

        elif float(balance['secondary_jpy']) <= float(self.minimum_yen_limit):
            log.critical(self.SECONDARY_BROKER + 'の円残高が下限に達しました。')
            direction = "reverse"
            primary_trade_type = "buy"
            secondary_trade_type = "sell"

        elif float(balance['secondary_btc']) <= float(self.minimum_btc_limit):
            log.critical(self.SECONDARY_BROKER + 'のBTC残高が下限に達しました。')
            direction = "reverse"
            primary_trade_type = "sell"
            secondary_trade_type = "buy"

        else:
            direction = "forward"
            primary_trade_type = ''
            secondary_trade_type = ''

        info = {
                    "direction":direction,
                    "primary"  :primary_trade_type,
                    "secondary":secondary_trade_type
                }

        return info

    #####################################################
    #トレードを確実にするために、事前にした枚数の板の合計を取得する。
    #板の合計のロット数が、事前にしたロット数の事前に指定した倍数を超えている場合、トレードするようにする。
    #両方のブローカーの板情報を取得する。
    #両サイドのブローカの板情報を取得する。
    #####################################################
    def getTradableInfo(self,board,board_count):

        ask_lot = [0] * board_count
        bid_lot = [0] * board_count

        tradable_ask_lot = 0
        tradable_bid_lot = 0

        #board_countまでの板の枚数を安全率と考えて合計を算出する。
        for i in range(board_count):
            ask_lot[i] = float(board['asks'][i][1])
            bid_lot[i] = float(board['bids'][i][1])

            tradable_ask_lot += ask_lot[i]
            tradable_bid_lot += bid_lot[i]

        info = {}
        info['tradable_ask_lot'] = tradable_ask_lot 
        info['tradable_bid_lot'] = tradable_bid_lot 
        info['tradable_ask'] = float(board['asks'][board_count][0])
        info['tradable_bid'] = float(board['bids'][board_count][0])

        return info

    #主ブローカーで買い、副ブローカーで売り
    def primaryBuySecondarySell(self,lot,p_ask,s_bid):

        log.critical("####################################################")
        log.critical(self.PRIMARY_BROKER + ":買い " + self.SECONDARY_BROKER + ":売り")
        log.critical("####################################################")

        if self.mode == "production":
            #primaryで買う。
            self.primary.marketAsk(lot,p_ask)
            #secondarycheckで売る。
            self.secondary.marketBid(lot,s_bid)

    #主ブローカーで売り、副ブローカーで買い
    def primarySellSecondaryBuy(self,lot,s_ask,p_bid):

        log.critical("####################################################")
        log.critical(self.PRIMARY_BROKER + ":売り " + self.SECONDARY_BROKER + ":買い")
        log.critical("####################################################")

        if self.mode == "production":
            #secondaryで買う。
            self.secondary.marketAsk(lot,s_ask)
            #primaryで売る。
            self.primary.marketBid(lot,p_bid)
           
    #フォワードトレードが可能な状態の発生回数をカウントする。
    def countForwardTradableTime(self,p_info,s_info):
        self.countTradableTime(self.entry_spread,p_info,s_info)

    #リバーストレードが可能な状態の発生回数をカウントする。
    def countReverseTradableTime(self,p_info,s_info):
        self.countTradableTime(self.reverse_spread,p_info,s_info)

    #価格とロットがトレード可能なしきい値を超えた回数をカウントする。
    def countTradableTime(self,spread,p_info,s_info):

        if( p_info['tradable_bid'] > s_info['tradable_ask'] and
            p_info['tradable_bid'] - s_info['tradable_ask'] > spread and
            p_info['tradable_bid_lot'] > self.tradable_lot and
            s_info['tradable_ask_lot'] > self.tradable_lot ):

            self.primary_tradable_time += 1
            self.secondary_tradable_time = 0

        elif(   s_info['tradable_bid'] > p_info['tradable_ask'] and
                s_info['tradable_bid'] - p_info['tradable_ask'] > spread and
                s_info['tradable_bid_lot'] > self.tradable_lot and
                p_info['tradable_ask_lot'] > self.tradable_lot ):

            self.primary_tradable_time = 0
            self.secondary_tradable_time += 1

        else:
            self.primary_tradable_time = 0
            self.secondary_tradable_time = 0

    #通常方向のトレードを行う。
    def forwardTrade(self,p_info,s_info):
 
        log.critical("##### Action Mode:FORWARD")

        if self.primary_tradable_time >= self.price_over_count:

            self.primaryBuySecondarySell(self.btc_lot,p_info['tradable_ask'],s_info['tradable_bid'])
            self.primary_tradable_time = 0
            self.secondary_tradable_time = 0
            
        elif self.secondary_tradable_time >= self.price_over_count:

            self.primarySellSecondaryBuy(self.btc_lot,p_info['tradable_bid'],s_info['tradable_ask'])
            self.primary_tradable_time = 0
            self.secondary_tradable_time = 0

        return

    #リバース方向へのトレードを行う。
    def reverseTrade(self,status,p_info,s_info):

        log.critical("##### Action Mode:REVERSE")

        if status['primary'] == 'buy' and status['secondary'] == 'sell':
            self.primaryBuySecondarySell(self.btc_lot,p_info['tradable_ask'],s_info['tradable_bid'])
            self.primary_tradable_time = 0
            self.secondary_tradable_time = 0

        elif status['primary'] == 'sell' and status['secondary'] == 'buy':
            self.primarySellSecondaryBuy(self.btc_lot,p_info['tradable_bid'],s_info['tradable_ask'])
            self.primary_tradable_time = 0
            self.secondary_tradable_time = 0

        return

    def showConsoleLog(self,balance,p_info,s_info,pt_info,st_info):
        log.critical("##### 残高")
        log.critical(self.PRIMARY_BROKER   + ":" + str(balance['primary_jpy']))
        log.critical(self.SECONDARY_BROKER + ":" + str(balance['secondary_jpy']))
        log.critical(self.PRIMARY_BROKER   + "-BTC:" + str(balance['primary_btc']))
        log.critical(self.SECONDARY_BROKER + "-BTC:" + str(balance['secondary_btc']))
        log.critical("TOTAL JPY:" + str(balance['primary_jpy'] + balance['secondary_jpy']))
        log.critical("TOTAL BTC:" + str(balance['primary_btc'] + balance['secondary_btc']))
        log.critical("-----------------------------------------------------------------")

        log.critical("-------------------- Price")
        log.critical(self.PRIMARY_BROKER   + ":Ask " + str(p_info['asks'][0]))
        log.critical(self.PRIMARY_BROKER +   ":Bid " + str(p_info['bids'][0]))
        log.critical(self.SECONDARY_BROKER + ":Ask " + str(s_info['asks'][0]))
        log.critical(self.SECONDARY_BROKER + ":Bid " + str(s_info['bids'][0]))

        log.critical("-------------------- Best Price Difference")
        log.critical(self.PRIMARY_BROKER   + ":bid-" + self.SECONDARY_BROKER + ":ask " + str(float(p_info['bids'][0][0]) - float(s_info['asks'][0][0])))
        log.critical(self.SECONDARY_BROKER + ":bid-" + self.PRIMARY_BROKER   + ":ask " + str(float(s_info['bids'][0][0]) - float(p_info['asks'][0][0])))
        log.critical("-------------------- Tradable Price Difference")
        log.critical(self.PRIMARY_BROKER   + ":bid-" + self.SECONDARY_BROKER + ":ask " + str(float(pt_info['tradable_bid']) - float(st_info['tradable_ask'])))
        log.critical(self.SECONDARY_BROKER + ":bid-" + self.PRIMARY_BROKER   + ":ask " + str(float(st_info['tradable_bid']) - float(pt_info['tradable_ask'])))

        log.critical("-----------------------------------------------------------------")

    #メイン処理
    def mainProcess(self):

        #メインループに入る。
        while True:

            #残高情報を更新する。
            self.updateBalance()

            #口座残高を取得して、インスタンスに保持する。
            self.balance = self.getBalance()

            #残高状態をチェックしてトレード方向を取得する。
            trade_status = self.checkBalance(self.balance) 
            self.action_mode = trade_status['direction']

            #板情報を取得する。
            primary_info   = self.primary.getBoard()
            secondary_info = self.secondary.getBoard()

            #トレード可能なロット数と価格を取得する。
            primary_tradable_info   = self.getTradableInfo(primary_info,self.board_count)
            secondary_tradable_info = self.getTradableInfo(secondary_info,self.board_count)

            #forwardモードに入る。
            if self.action_mode == 'forward':
                log.critical("##### Action Mode:SPREAD")

                #トレード可能な状態になっている回数をカウントしてプロパティに設定する。
                self.countForwardTradableTime(primary_tradable_info,secondary_tradable_info)

                #通常方向へのトレードを行う。
                self.forwardTrade(primary_tradable_info,secondary_tradable_info)


            #JPY残高または、BTC残高が足りない場合は、リバースモード（偏り解消モード）に入る。
            else:
                log.critical("##### Action Mode:REVERSE")

                #トレード可能な状態になっている回数をカウントしてプロパティに設定する。
                self.countReverseTradableTime(primary_tradable_info,secondary_tradable_info)

                #リバース方向へのトレードを行う。
                self.reverseTrade(trade_status,primary_tradable_info,secondary_tradable_info)

            self.showConsoleLog(self.balance,primary_info,secondary_info,primary_tradable_info,secondary_tradable_info)

            #指定時間停止する。
            time.sleep(self.interval_second)


if __name__ == "__main__":

    try:      
        BrokerArbiTrage('liquid','coincheck').mainProcess()
    except Exception as e:
        t = traceback.format_exc()
        log.critical(t)
        slack.Slack.post_message(t)

