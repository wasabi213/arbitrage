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
log = Logger(__name__)

class ZaifCoincheckTrade:

    def __init__(self):
        self.conf = configparser.ConfigParser() 
        self.conf.read_file(codecs.open(CONFIG_FILE,"r","utf8"))

        self.LOG_PATH = self.conf.get('path','trade_log_path') 

        #--------------------------------------------------------------------
        #動作モード
        self.mode = self.conf.get('env','mode')
        #日本円の最小限度額
        self.minimum_yen_limit = self.conf.getint('trade','minimum_yen_limit')
        #BTCの最小限度額
        self.minimum_btc_limit = self.conf.getfloat('trade','minimum_btc_limit')

        #１度にエントリするBTCの枚数
        self.btc_lot = self.conf.getfloat('trade','btc_lot')

        #ブローカに最初に置いたBTCの枚数(両方のブローカに同じ枚数を配置する。)
        self.btc_start_amount = self.conf.getfloat('trade','btc_start_amount')

        #スプレッドモードで動作しているか、リバースモードで動作しているか。
        self.action_mode = ''

        #エントリするときのスプレッド
        self.entry_spread = self.conf.getint('trade','entry_spread')
        #リバースするときのスプレッド
        self.reverse_spread = self.conf.getint('trade','reverse_spread')

        #zaifのスプレッドがしきい値を超えた回数
        self.zaif_spread_over_count = 0
        #coincheckのスプレッドがしきい値を超えた回数
        self.coin_spread_over_count = 0

        #何枚目の板まで読むか。（枚数で指定）
        self.board_count = self.conf.getint('trade','board_count')

        #エントリロットするに対する指値に入っているロットの倍率
        self.entry_rate = self.conf.getint('trade','entry_rate')

        #スプレッドが何回連続で閾値を超えたらエントリするか。
        self.price_over_count = self.conf.getint('trade','price_over_count')

        #何秒ごとに処理を行うか。（秒）
        self.interval_second = self.conf.getint('trade','interval_second')

        #どちらのブローカーにBTCを戻すか。
        self.reverse_broker = ''

        #最新の残高状態
        self.balance = []

        #ZaifAPI
        self.zaif_api = zaif_api.ZaifApi()
        #CoincheciAPI
        self.coin_api = coincheck_api.CoincheckApi()
        
        #DEBUG用残高ファイル
        self.DEBUG_BALANCE_FILE = self.conf.get('debug','DEBUG_BALANCE_FILE')

    #status_logを作成する。
    def create_debug_log(self):
        #ディレクトリを取得する。
        if os.path.exists(self.DEBUG_BALANCE_FILE) == False:
            with open(self.DEBUG_BALANCE_FILE,"w") as w:
                balance = {
                            'zaif_jpy': self.conf.get('debug','zaif_jpy'),
                            'zaif_btc': self.conf.get('debug','zaif_btc'),
                            'coin_jpy': self.conf.get('debug','coincheck_jpy'),
                            'coin_btc': self.conf.get('debug','coincheck_btc'),
                          }

                json.dump(balance,w)
            log.critical("デバッグ用残高ファイルを作成しました。")

    #zaifとcoinncheckの残高を取得する。
    def getBalance(self):

        balance = {}
        if self.mode == 'production':
            zaif_balance_info = self.zaif_api.zaif_get_info2()
            zaif_balance_jpy = self.zaif_api.zaif_get_balance_jpy(zaif_balance_info)
            zaif_balance_btc = self.zaif_api.zaif_get_balance_btc(zaif_balance_info)

            coin_balance_info = self.coin_api.coin_get_balance()
            coin_balance_jpy = self.coin_api.coin_get_balance_jpy(coin_balance_info)
            coin_balance_btc = self.coin_api.coin_get_balance_btc(coin_balance_info)

            balance = { 'zaif_jpy':int(zaif_balance_jpy),
                        'zaif_btc':float(zaif_balance_btc),
                        'coin_jpy':float(coin_balance_jpy),
                        'coin_btc':float(coin_balance_btc)
                        }

        else:
            debug_balance_file = self.conf.get('debug','DEBUG_BALANCE_FILE')
            with open(debug_balance_file,"r") as f:
                line = f.readline()
                jb = json.loads(line)
               
            balance = { 'zaif_jpy':  int(jb['zaif_jpy']),
                        'zaif_btc':float('{:.3f}'.format(float(jb['zaif_btc']))),
                        'coin_jpy':  int(jb['coin_jpy']),
                        'coin_btc':float('{:.3f}'.format(float(jb['coin_btc'])))
                        }

        return balance

    #円残高、BTC残高が十分にあるかチェックする。
    def checkBalance(self,balance):

        if int(balance['coin_jpy']) <= int(self.minimum_yen_limit):
            log.critical('Coincheckの円残高が下限に達しました。')
            log.critical('Coincheckの残高は、￥' + str(balance['coin_jpy']) + 'です。')
            log.info('coincheckの残高の下限は' + str(self.minimum_yen_limit) + 'です。')
            return False

        elif float(balance['coin_btc']) <= float(self.minimum_btc_limit):
            log.critical('CoincheckのBTC残高が下限に達しました。')
            return False

        elif int(balance['zaif_jpy']) <= int(self.minimum_yen_limit):
            log.critical('zaifの円残高が下限に達しました。')
            return False

        elif float(balance['zaif_btc']) <= float(self.minimum_btc_limit):
            log.critical('zaifのBTC残高が下限に達しました。')
            return False

        return True

    #####################################################
    #トレードを確実にするために、事前にした枚数の板の合計を取得する。
    #板の合計のロット数が、事前にしたロット数の事前に指定した倍数を超えている場合、トレードするようにする。
    #両方のブローカーの板情報を取得する。
    #両サイドのブローカの板情報を取得する。
    #####################################################
    def getBoardInfoWithCount(self,board_count,entry_rate):

        #戻り値
        #zaifのaskの板の１枚目、２枚目、３枚目のそれぞれの価格とロット
        #zaifのbidの板の１枚目、２枚目、３枚目のそれぞれの価格とロット
        #coincheckのaskの板の１枚目、２枚目、３枚目のそれぞれの価格とロット
        #coincheckのbidの板の１枚目、２枚目、３枚目のそれぞれの価格とロット
        #zaifとcoincheckの指定した番号の板の価格の差額

        zaif_ask     = [0] * board_count
        zaif_ask_lot = [0] * board_count
        zaif_bid     = [0] * board_count
        zaif_bid_lot = [0] * board_count
        coin_ask     = [0] * board_count
        coin_ask_lot = [0] * board_count
        coin_bid     = [0] * board_count
        coin_bid_lot = [0] * board_count

        zaif_tradable_ask_price = 0
        zaif_tradable_bid_price = 0
        coin_tradable_ask_price = 0
        coin_tradable_bid_price = 0

        zaif_tradable_ask_lot_total = 0 
        zaif_tradable_bid_lot_total = 0
        coin_tradable_ask_lot_total = 0
        coin_tradable_bid_lot_total = 0

        za_cb_board_count_price = 0
        ca_zb_board_count_price = 0

        coin_result = self.coin_api.coincheck_get_board()
        zaif_result = self.zaif_api.zaif_get_board()

        for i in range(board_count):
            zaif_ask[i]     = float(zaif_result['asks'][i][0])
            zaif_ask_lot[i] = float(zaif_result['asks'][i][1])
            zaif_bid[i]     = float(zaif_result['bids'][i][0])
            zaif_bid_lot[i] = float(zaif_result['bids'][i][1])

            coin_ask[i]     = float(coin_result['asks'][i][0])
            coin_ask_lot[i] = float(coin_result['asks'][i][1])
            coin_bid[i]     = float(coin_result['bids'][i][0])
            coin_bid_lot[i] = float(coin_result['bids'][i][1])

            zaif_tradable_ask_lot_total += zaif_ask_lot[i]
            zaif_tradable_bid_lot_total += zaif_bid_lot[i]
            coin_tradable_ask_lot_total += coin_ask_lot[i]
            coin_tradable_bid_lot_total += coin_ask_lot[i]

        zaif_tradable_ask_price = float(zaif_result['asks'][board_count][0])
        zaif_tradable_bid_price = float(zaif_result['bids'][board_count][0])
        coin_tradable_ask_price = float(coin_result['asks'][board_count][0])
        coin_tradable_bid_price = float(coin_result['bids'][board_count][0])

        za_cb_board_count_price = zaif_tradable_ask_price - coin_tradable_bid_price
        ca_zb_board_count_price = coin_tradable_ask_price - zaif_tradable_bid_price 

        info = { 
                    'zaif_ask':zaif_ask,
                    'zaif_bid':zaif_bid,
                    'coin_ask':coin_ask,
                    'coin_bid':coin_bid,
                    'zaif_ask_lot':zaif_ask_lot,
                    'zaif_bid_lot':zaif_bid_lot,
                    'coin_ask_lot':coin_ask_lot,
                    'coin_bid_lot':coin_bid_lot,
                    'zaif_tradable_ask_lot_total':zaif_tradable_ask_lot_total,
                    'zaif_tradable_bid_lot_total':zaif_tradable_bid_lot_total,
                    'coin_tradable_ask_lot_total':coin_tradable_ask_lot_total,
                    'coin_tradable_bid_lot_total':coin_tradable_bid_lot_total,
                    'zaif_tradable_ask_price':zaif_tradable_ask_price,
                    'zaif_tradable_bid_price':zaif_tradable_bid_price,
                    'coin_tradable_ask_price':coin_tradable_ask_price,
                    'coin_tradable_bid_price':coin_tradable_bid_price,
                    'za_cb_board_count_price':za_cb_board_count_price,
                    'ca_zb_board_count_price':ca_zb_board_count_price,
                }

        return info

    #トレード方向を取得する      
    def getTradeType(self,board):

        trade_type = ''
        price_diff = 0

        #トレード方向を確認する。
        if board['za_cb_board_count_price'] > board['ca_zb_board_count_price']:
            trade_type = 'za_cb'
            price_diff = board['za_cb_board_count_price']

        elif board['ca_zb_board_count_price'] > board['za_cb_board_count_price']:
            trade_type = 'ca_zb'
            price_diff = board['ca_zb_board_count_price']

        elif board['za_cb_board_count_price'] == board['ca_zb_board_count_price']:
            trade_type = ''
            price_diff = 0

        else:
            log.critical(board)         
            raise Exception

        return {'trade_type':trade_type,'price_diff':price_diff}


    def debugWriteBalance(self,balance):

        debug_balance_file = self.conf.get('debug','DEBUG_BALANCE_FILE')

        #TESTモードでファイルへ書き込み
        with open(debug_balance_file,"w") as w:
            json.dump(balance,w)


    #Zaifで買ってCoincheckで売る。
    def TradeBuyZaifSellCoincheck(self,btc_lot,zaif_ask,coin_bid):
        log.critical("####################################")
        log.critical("##### BUY => Zaif  SELL => Coincheck")
        log.critical("####################################")

        if self.mode == "production":
            #zaifで買う。
            self.zaif_api.trade_zaif_ask(btc_lot,zaif_ask)
            #coincheckで売る。
            self.coin_api.trade_coin_bid(btc_lot)
            #zaifとコインチェックの残高を取得する。
            balance = self.getBalance()

        else:
            balance_before = self.getBalance()
            #zaifで買った価格と数量を出力する。
            zaif_jpy = int(balance_before['zaif_jpy']) - (btc_lot * zaif_ask)
            zaif_btc = float(balance_before['zaif_btc']) + btc_lot
            #coincheckで売った価格と数量を出力する。
            coin_jpy = int(balance_before['coin_jpy']) + (btc_lot * coin_bid)
            coin_btc = float(balance_before['coin_btc']) - btc_lot

            log.critical("coin_ask:" + str(zaif_ask))
            log.critical("zaif_bid:" + str(coin_bid))

            balance = {
                                'zaif_jpy':zaif_jpy,
                                'zaif_btc':zaif_btc,
                                'coin_jpy':coin_jpy,
                                'coin_btc':coin_btc
                            }
 
            self.debugWriteBalance(balance)


    #Coincheckで買ってZaifで売る。
    def TradeBuyCoincheckSellZaif(self,btc_lot,coin_ask,zaif_bid):
        log.critical("####################################")
        log.critical("##### BUY => Coincheck  SELL => Zaif")
        log.critical("####################################")

        if self.mode == "production":
            #Coincheckで買う
            self.coin_api.trade_coin_ask(btc_lot,coin_ask)
            #zaifで売る。
            self.zaif_api.trade_zaif_bid(btc_lot,zaif_bid)
            #zaifとコインチェックの残高を取得する。
            balance = self.getBalance()

        else:
            balance_before = self.getBalance()
            #Coincheckで買った価格と数量を出力する。
            coin_jpy = int(balance_before['coin_jpy']) - (btc_lot * coin_ask)
            coin_btc = float(balance_before['coin_btc']) + btc_lot

            #coincheckで売った価格と数量を出力する。
            zaif_jpy = int(balance_before['zaif_jpy']) + (btc_lot * zaif_bid)
            zaif_btc = float(balance_before['zaif_btc']) - btc_lot

            log.critical("coin_ask:" + str(coin_ask))
            log.critical("zaif_bid:" + str(zaif_bid))

            balance = {
                                'zaif_jpy':zaif_jpy,
                                'zaif_btc':zaif_btc,
                                'coin_jpy':coin_jpy,
                                'coin_btc':coin_btc
                            }
 
            self.debugWriteBalance(balance)

    #スプレッド取引を行う。
    def spreadAction(self,board,board_info):

        #実際にトレードする枚数の指定倍が板に入っているか。
        tradable_lot = self.btc_lot * self.entry_rate

        if(board['coin_tradable_bid_price'] > board['zaif_tradable_ask_price'] and
           board['coin_tradable_bid_price'] - board['zaif_tradable_ask_price'] > self.entry_spread and
           board['coin_tradable_bid_lot_total'] > tradable_lot and 
           board['zaif_tradable_ask_lot_total'] > tradable_lot):

            self.zaif_spread_over_count += 1
            self.coin_spread_over_count = 0

        elif(board['zaif_tradable_bid_price'] > board['coin_tradable_ask_price'] and
             board['zaif_tradable_bid_price'] - board['coin_tradable_ask_price'] > self.entry_spread and
             board['zaif_tradable_bid_lot_total'] > tradable_lot and 
             board['coin_tradable_ask_lot_total'] > tradable_lot):

            self.coin_spread_over_count += 1
            self.zaif_spread_over_count = 0
        else:
            self.zaif_spread_over_count = 0
            self.coin_spread_over_count = 0

        if self.zaif_spread_over_count >= self.price_over_count:
            #Zaifで買ってCoincheckで売る。
            self.TradeBuyZaifSellCoincheck( self.btc_lot,
                                            board['zaif_tradable_ask_price'],
                                            board['coin_tradable_bid_price'])
            self.zaif_spread_over_count = 0
            self.coin_spread_over_count = 0
            
        elif self.coin_spread_over_count >= self.price_over_count:
            #Coincheckで買って、Zaifで売る。
            self.TradeBuyCoincheckSellZaif( self.btc_lot,
                                            board['coin_tradable_ask_price'],
                                            board['zaif_tradable_bid_price'])
            self.zaif_spread_over_count = 0
            self.coin_spread_over_count = 0

        return


    def reverseToZaif(self,board,info):
        log.critical('trade_type:' + info['trade_type'])
        log.critical('price_diff:' + str(info['price_diff']))

        #実際にトレードする枚数の指定倍が板に入っているか。
        tradable_lot = self.btc_lot * self.entry_rate

        if(board['coin_tradable_bid_price'] > board['zaif_tradable_ask_price'] and
           board['coin_tradable_bid_price'] - board['zaif_tradable_ask_price'] > self.reverse_spread and
           board['coin_tradable_bid_lot_total'] > tradable_lot and 
           board['zaif_tradable_ask_lot_total'] > tradable_lot):

            self.coin_spread_over_count = 0
            self.zaif_spread_over_count += 1
        else:
            self.coin_spread_over_count = 0
            self.zaif_spread_over_count = 0

        log.critical("リバーススプレッド閾値超過回数：" + str(self.zaif_spread_over_count))

        #連続でスプレッドが開いていた場合
        if self.zaif_spread_over_count >= self.price_over_count:

            #Zaifで買ってCoincheckで売る。
            self.TradeBuyZaifSellCoincheck( self.btc_lot,
                                            board['zaif_tradable_ask_price'],
                                            board['coin_tradable_bid_price'])
            self.zaif_spread_over_count = 0
            self.coin_spread_over_count = 0

        return

    def reverseToCoincheck(self,board,info):

        log.critical('trade_type:' + info['trade_type'])
        log.critical('price_diff:' + str(info['price_diff']))

        #実際にトレードする枚数の指定倍が板に入っているか。
        tradable_lot = self.btc_lot * self.entry_rate

        #Coincheckの買い、Zaifの売りで、リバーススプレッドより値幅が開いた場合
        if(board['zaif_tradable_bid_price'] > board['coin_tradable_ask_price'] and
           board['zaif_tradable_bid_price'] - board['coin_tradable_ask_price'] > self.reverse_spread and
           board['zaif_tradable_bid_lot_total'] > tradable_lot and 
           board['coin_tradable_ask_lot_total'] > tradable_lot):

            self.coin_spread_over_count += 1
            self.zaif_spread_over_count = 0
        else:
            self.coin_spread_over_count = 0
            self.zaif_spread_over_count = 0

        log.critical("リバーススプレッド閾値超過回数：" + str(self.coin_spread_over_count))

        #連続でスプレッドが開いていた場合           
        if self.coin_spread_over_count >= self.price_over_count:
            #Coincheckで買って、Zaifで売る。
            self.TradeBuyCoincheckSellZaif( self.btc_lot,
                                            board['coin_tradable_ask_price'],
                                            board['zaif_tradable_bid_price']
                                            )
            self.zaif_spread_over_count = 0
            self.coin_spread_over_count = 0


    #メイン処理
    def mainProcess(self):

        if self.mode != 'production':
            self.create_debug_log()

        #メインループに入る。
        while True:


            #口座残高を取得して、インスタンスに保持する。
            self.balance = self.getBalance()
            log.critical("##### 残高")
            log.critical("         Zaif:" + str(self.balance['zaif_jpy']))
            log.critical("    Coincheck:" + str(self.balance['coin_jpy']))
            log.critical("     Zaif-BTC:" + str(self.balance['zaif_btc']))
            log.critical("Coincheck-BTC:" + str(self.balance['coin_btc']))
            log.critical("TOTAL JPY:" + str(self.balance['zaif_jpy'] + self.balance['coin_jpy']))
            log.critical("TOTAL BTC:" + str(self.balance['zaif_btc'] + self.balance['coin_btc']))
            log.critical("-----------------------------------------------------------------")

            #指定時間停止する。
            time.sleep(self.interval_second)



            #残高チェックを行う。
            #1度下限に到達したら、もとに戻るまでそのままにする必要があるがこれではだめだと思う。
            if ( self.action_mode == 'spread' and 
                 self.checkBalance(self.balance) == False ):
                self.action_mode = 'reverse'

                if self.balance['zaif_btc'] > self.balance['coin_btc']:
                    self.reverse_broker = 'ZTOC'
                else:
                    self.reverse_broker = 'CTOZ'
                log.critical('SPREAD -> REVERSE')

            elif self.action_mode == 'reverse':

                #
                # 最初の残高に戻るまで待たずに、btcの最低残高に戻ったら、エントリできるようにする。
                #
                if( self.reverse_broker == 'ZTOC' and
                    self.balance['coin_btc'] >= self.minimum_btc_limit and
                    self.balance['zaif_jpy'] >= self.minimum_yen_limit ):

                    self.action_mode = 'spread'
                    self.reverse_broker = ''
                    log.critical('REVERSE -> SPREAD')

                elif( self.reverse_broker == 'CTOZ' and
                      self.balance['zaif_btc'] >= self.minimum_btc_limit and
                      self.balance['coin_jpy'] >= self.minimum_yen_limit ):

                    self.action_mode = 'spread'
                    self.reverse_broker = ''
                    log.critical('REVERSE -> SPREAD')
                else:
                    pass
            else:
                self.action_mode = 'spread'
                self.reverse_broker = ''

            #板情報を取得する。
            board = self.getBoardInfoWithCount(self.board_count,self.entry_rate)
            #トレード方向を取得する。
            board_info = self.getTradeType(board)

            if self.action_mode == 'spread':
                #Spreadモードに入る。
                log.critical("##### Action Mode:SPREAD")
                self.spreadAction(board,board_info)

            #残高が足りない場合は、リバースモード（偏り解消モード）に入る。
            else:
                log.critical("##### Action Mode:REVERSE")

                if self.balance['zaif_btc'] >  self.balance['coin_btc']:
                    log.critical("BUY:Coincheck SELL:Zaif")
                    log.critical("BTC      Zaif => Coincheck")
                    log.critical("JPY Coincheck => Zaif")
                    self.reverseToCoincheck(board,board_info)

                elif self.balance['coin_btc'] > self.balance['zaif_btc']:
                    log.critical("BUY:Zaif SELL:Coincheck")
                    log.critical("BTC Coincheck => Zaif")
                    log.critical("JPY      Zaif => Coincheck")
                    self.reverseToZaif(board,board_info)
                else:
                    pass

            log.critical("-------------------- Price")
            log.critical("Zaif:Ask " + str(board['zaif_ask'][0]))
            log.critical("Zaif:Bid " + str(board['zaif_bid'][0]))
            log.critical("Coincheck:Ask " + str(board['coin_ask'][0]))
            log.critical("Coincheck:Bid " + str(board['coin_bid'][0]))

            log.critical("-------------------- Best Price Difference")
            log.critical("ZA-CB:" + str(board['coin_bid'][0] - board['zaif_ask'][0]))
            log.critical("CA-ZB:" + str(board['zaif_bid'][0] - board['coin_ask'][0]))
            log.critical("-------------------- Tradable Price Difference")
            log.critical("ZA-CB:" + str(board['coin_tradable_bid_price'] - board['zaif_tradable_ask_price'] ))
            log.critical("CA-ZB:" + str(board['zaif_tradable_bid_price'] - board['coin_tradable_ask_price'] ))

            log.critical("-----------------------------------------------------------------")







if __name__ == "__main__":

    try:      
        ZaifCoincheckTrade().mainProcess()
    except Exception as e:
        t = traceback.format_exc()
        log.critical(t)
        slack.Slack.post_message(t)

