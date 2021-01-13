# coding:utf-8
####import設定####
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
from api import zaif_api,coincheck_api
from common import spreadlog,slack


CONFIG_FILE = '../config/zaif_coincheck_config.ini'
MODE = "test"

log = logger.Logger(__name__)

####初期設定値####
#api設定

#初期値
btc = 0.005 #取引量設定（0.006以上推奨※最低取引量は0.005）
freq = 3 #繰り返し周期[sec]
spread_Th = 1000 #「差が十分広がっている」とみなすしきい値
unspread_Th = 500 #「差が十分閉じている」とみなすしきい値

entry_rate = 2 # 取引したいbtcの量の何倍の指値が板に入っていたらエントリするかの値

spread_count_Th = 2 #このしきい値以上の回数spread_Thを満たせば取引実施
unspread_count_Th = 2 #このしきい値以上の回数unspread_Thを満たせば逆取引実施
retry_count_Th = 100 #サーバ接続エラーなどでプログラムが停止したとき、このしきい値の回数リトライ実施
retry_freq = 3  #リトライ実施時のwait time[sec]
flag = -1

class ZaifCoincheckTrade:

    def __init__(self):
        self.conf = configparser.ConfigParser() 
        self.conf.readfp(codecs.open(CONFIG_FILE,"r","utf8"))
        self.LOG_PATH = self.conf.get('path','trade_log_path') 
        self.cc_api = coincheck_api.CoincheckApi()
        self.zaif_api = zaif_api.ZaifApi()
        self.TRADE_FLAG = -1

        self.open_spread = self.conf.getint('trade','open_spread')
        self.close_spread = self.conf.getint('trade','close_spread')

        self.zaif_yen_amount = 100000 #日本円初回残高
        self.zaif_btc_amount = 0.1    #BTC初回残高
        self.coincheck_yen_amount = 100000 #日本円初回残高
        self.coincheck_btc_amount = 0.1    #BTC初回残高

    ##############
    #log入力用関数
    ##############
    def logreader(self):
        f = open(self.LOG_PATH,'r')

        reader = csv.reader(f)
        f.close

        if reader.line_num == 0:
            self.TRADE_FLAG = 0
            return(self.TRADE_FLAG)

        for row in reader:

            lastrow = row

            last_trade_status = lastrow[1]

            if len(lastrow) >= 11:
                last_trade_type = lastrow[11]

            if last_trade_status == 'unspread':
                #spread待ち状態
                self.TRADE_FLAG = 0

            elif last_trade_status == 'ccerror':
                log.critical('CoinCheckでエラーが発生した履歴があります。プログラムスタートさせません。')
                sys.exit()

            else:
            #last_trade_status = 'spread'
            #unspreadをしないで閉じてしまっている。

                if last_trade_type == 'za_cb':
                    #spread時にza_cbをやってしまっている。
                    #unspread時にはca_zbで取引をする必要がある。
                    self.TRADE_FLAG = 1
                if last_trade_type == 'ca_zb':
                    #spread時にca_zbをやってしまっている。
                    #unspread時にはza_cbで取引をする必要がある。
                    self.TRADE_FLAG = 2

                if lastrow[15] == none or lastrow[15] == '' or lastrow[16] == none or lastrow[16] == '':
                    log.critical('前回のspreadが記録されていません。')
                    sys.exit()

                self.open_spread = lastrow[15]
                self.close_spread = lastrow[16]

        return(self.TRADE_FLAG)

    #スタート時のパラメータ表示
    def showParameter(self):
        log.critical('flag:'+str(self.TRADE_FLAG))
        #初期値の表示
        log.critical('設定取引量：'+ str(btc) + 'btc')
        log.critical('繰り返し周期：'+ str(freq) + 'sec')
        log.critical('リトライ繰り返し周期：'+ str(retry_freq) + 'sec')
        log.critical('spreadしきい値：'+str(spread_Th)+ 'yen')
        log.critical('unspreadしきい値：'+str(unspread_Th)+ 'yen')
        log.critical('spreadカウントしきい値:'+str(spread_count_Th)+'回')
        log.critical('unspreadカウントしきい値:'+str(unspread_count_Th)+'回')
        log.critical('リトライカウントしきい値:'+str(retry_count_Th)+'回')
        log.critical('ArbitrageProgram を開始します : '+str(datetime.datetime.now()))

    def getBrokerTicker(self):
        #zaif_ticker取得
        for i in range(retry_count_Th):
            try:
                zaif = ZaifPublicApi()
                zaif_data_dict = zaif.ticker('btc_jpy')
            except:
                log.info('zaif_Error:ticker_待機します。 '+str(i)+'回目')
                time.sleep(retry_freq)
            else:
                break
        else:
            log.error('リトライが全て失敗しました。プログラムを停止します。')
            sys.exit()
            
        #coincheck_ticker取得
        for i in range(retry_count_Th):
            try:
                coin_data_dict = json.loads(self.cc_api.coin_get_ticker())
            except:
                log.info('coin_Error:ticker_待機します。 '+str(i)+'回目')
                time.sleep(retry_freq)
            else:
                break
        else:
            log.error('リトライが全て失敗しました。プログラムを停止します。')
            sys.exit()

    #フラグの状態を取得する。spread待ちか、unspread待ちか。
    def getStatus(self):
        if self.TRADE_FLAG == 0:
            status = 'spread待ち'
        else:
            status = 'unspread待ち'

        return status

    def printBrokerBoardDetail(self,coin_bid,coin_ask,zaif_bid,zaif_ask,coin_bid_lot,coin_ask_lot,zaif_bid_lot,zaif_ask_lot,za_cb,ca_zb):
        log.info("zaif_ask:" + "{:,.0f}".format(zaif_ask))
        log.info("zaif_bid:" + "{:,.0f}".format(zaif_bid))
        log.info("coin_ask:" + "{:,.0f}".format(coin_ask))
        log.info("coin_bid:" + "{:,.0f}".format(coin_bid))
        log.info("za_cb: coin_bid - zaif_ask = " + "{:,.0f}".format(za_cb))
        log.info("ca_zb: zaif_bid - coin_ask = " + "{:,.0f}".format(ca_zb))

        log.info("coincheck " + "BUY:" + "{:,.0f}".format(coin_bid) + "," + str(coin_bid_lot) + 
                " SELL:" + "{:,.0f}".format(coin_ask) + "," + str(coin_ask_lot))
        log.info("zaif " + "BUY:" + "{:,.0f}".format(zaif_bid) + "," + str(zaif_bid_lot) + 
                " SELL:" + "{:,.0f}".format(zaif_ask) + "," + str(zaif_ask_lot))
        log.info(self.getStatus() + ' za_cb:' + str(za_cb) + ' ca_zb:' + str(ca_zb))


    #zaifとcoinncheckの残高を取得する。
    def get_balance(self):

        zaif_balance_info = self.zaif_api.zaif_get_info2()
        zaif_balance_jpy = self.zaif_api.zaif_get_balance_jpy(zaif_balance_info)
        zaif_balance_btc = self.zaif_api.zaif_get_balance_btc(zaif_balance_info)

        coin_balance_info = self.coin_api.coin_get_balance()
        coin_balance_jpy = self.coin_api.coin_get_balance_jpy(zaif_balance_info)
        coin_balance_btc = self.coin_api.coin_get_balance_btc(zaif_balance_info)

        balance = { zaif_jpy:zaif_balance_jpy,
                    zaif_btc:zaif_balance_btc,
                    coin_jpy:coin_balance_jpy,
                    coin_btc:coin_balance_btc
                    }
        return balance

    #################################
    #アービトラージのメイン処理
    #################################
    def run(self):

        #初期化
        self.TRADE_FLAG = self.logreader() #前回終了時の取引状況の確認
        spread_count = 0
        unspread_count = 0

        self.showParameter()

        #以下繰り返し
        while True:

            #ブローカーからプライスが取得できることを確認する。
            self.getBrokerTicker()

            #板情報を取得する。
            coincheck_result = self.cc_api.coincheck_get_board()
            zaif_result = self.zaif_api.zaif_get_board()

            #lotを取得する。
            coin_bid_lot = float(self.cc_api.coincheck_get_board_bid_lot(coincheck_result))
            coin_ask_lot = float(self.cc_api.coincheck_get_board_ask_lot(coincheck_result))
            zaif_bid_lot = float(self.zaif_api.zaif_get_board_bid_lot(zaif_result))
            zaif_ask_lot = float(self.zaif_api.zaif_get_board_ask_lot(zaif_result))

            coin_bid_lot_sum = float(self.cc_api.coincheck_get_board_bid_lot_sum(coincheck_result,3))
            coin_ask_lot_sum = float(self.cc_api.coincheck_get_board_ask_lot_sum(coincheck_result,3))
            zaif_bid_lot_sum = float(self.zaif_api.zaif_get_board_bid_lot_sum(zaif_result,3))
            zaif_ask_lot_sum = float(self.zaif_api.zaif_get_board_ask_lot_sum(zaif_result,3))

            board_number = 3
            zaif_real_price = self.zaif_api.zaif_get_ticker_by_size(zaif_result,btc,board_number,entry_rate)
            coin_real_price = self.cc_api.coin_get_ticker_by_size(coincheck_result,btc,board_number,entry_rate)

            zaif_ask = float(zaif_real_price['ask'][0])
            zaif_bid = float(zaif_real_price['bid'][0])
            coin_ask = float(coin_real_price['ask'][0])
            coin_bid = float(coin_real_price['bid'][0])

            #bid値、ask値から損益を計算する
            za_cb = coin_bid - zaif_ask  #zaifで買ってcoincheckで売る
            ca_zb = zaif_bid - coin_ask  #coincheckで買ってzaifで売る  

            log.report(zaif_ask,zaif_bid,coin_ask,coin_bid,za_cb,ca_zb)

            #板の詳細情報を画面に表示する。
            self.printBrokerBoardDetail(coin_bid,coin_ask,zaif_bid,zaif_ask,coin_bid_lot,coin_ask_lot,zaif_bid_lot,zaif_ask_lot,za_cb,ca_zb)            

            #Check & Trade
            #フラグの状態を取得する。
            status = self.getStatus()

            if self.TRADE_FLAG == 0:
                if za_cb > ca_zb:
                    Trade_Type = 'za_cb'
                    Trade_result = za_cb
                else:
                    Trade_Type = 'ca_zb'
                    Trade_result = ca_zb

                if Trade_Type == 'za_cb':
                    if za_cb > spread_Th:
                        log.info("********************** Spread OK! ************************")
                        spread_count = spread_count + 1

                        #spreadが2回連続でしきい値を超えたら、フラグを設定する。
                        if spread_count >= spread_count_Th:
                            log.info("Lot OK!")
                            self.TRADE_FLAG = 1
                            spread_count = 0
                    else:
                        spread_count = 0
                else:
                    if ca_zb > spread_Th:
                        log.info("********************** Spread OK! ************************")
                        spread_count = spread_count + 1

                        #spreadが2回連続でしきい値を超えたら、フラグを設定する。
                        if spread_count >= spread_count_Th:
                            log.info("Lot OK!")
                            self.TRADE_FLAG = 2
                            spread_count = 0
                    else:
                        spread_count = 0

                if self.TRADE_FLAG == 0:
                    pass
                elif self.TRADE_FLAG == 1 or 2:
                    #spread:取引実施
                    if self.TRADE_FLAG == 1: #zaifで買って、coincheckで売る。
                        if MODE == "production":
                            #zaif_ask , coincheck_bid
                            #zaifで買う。
                            self.zaif_api.trade_zaif_ask(btc,zaif_ask)
                            #coincheckで売る。
                            self.cc_api.trade_coin_bid(btc)

                        else:
                            #zaifで買った価格と数量を出力する。
                            self.zaif_yen_amount = self.zaif_yen_amount - (btc * zaif_ask)
                            self.zaif_btc_amount = self.zaif_btc_amount + btc
                            #coincheckで売った価格と数量を出力する。
                            self.coincheck_yen_amount = self.coincheck_yen_amount + btc * coin_bid
                            self.coincheck_btc_amount = self.coincheck_btc_amount - btc
                            

                        #spreadした時の価格差を設定する。
                        self.open_spread = za_cb
                        log.critical('spread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - coincheck_bid : '+str(za_cb)+' JPY' )
                        slack.Slack.post_message('spread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - coincheck_bid : '+str(za_cb)+' JPY' )

                        #print("zaif 買い " + )


                    elif self.TRADE_FLAG ==2:
                        if MODE == "production":
                            #coincheck_ask , zaif_bid
                            #zaifで売る。
                            self.zaif_api.trade_zaif_bid(btc,zaif_bid)
                            #coincheckで買う。    
                            self.cc_api.trade_coin_ask(btc,coin_ask)
                        else:
                            #zaifで売った価格と数量を出力する。
                            self.zaif_yen_amount = self.zaif_yen_amount + (btc * zaif_bid)
                            self.zaif_btc_amount = self.zaif_btc_amount - btc
                            #coincheckで買った価格と数量を出力する。
                            self.coincheck_yen_amount = self.coincheck_yen_amount - btc * coin_ask
                            self.coincheck_btc_amount = self.coincheck_btc_amount + btc

                        #spreadした時の価格差を設定する。
                        self.open_spread = ca_zb
                        log.critical('spread動作実施 : '+str(datetime.datetime.now())+' coincheck_ask - zaif_bid : '+str(ca_zb)+' JPY' )
                        slack.Slack.post_message('spread動作実施 : '+str(datetime.datetime.now())+' coincheck_ask - zaif_bid : '+str(ca_zb)+' JPY' )

                    msg = (str(datetime.datetime.now()) +   ',spread,coin_bid,'+ str(coin_bid) + 
                                                            ',coin_ask,'+ str(coin_ask) + 
                                                            ',zaif_bid,' + str(zaif_bid) + 
                                                            ',zaif_ask,' + str(zaif_ask) + 
                                                            ',Trade_Type,' + str(Trade_Type) + 
                                                            ',Trade_result,' + str(Trade_result) +
                                                            ',open_spread,' + str(self.open_spread) +
                                                            ',close_spread,' + str(self.close_spread) + '\n')

                    spreadlog.log_output(self.LOG_PATH,msg)
                    #LINE_BOT(msg)
            else:
                if self.TRADE_FLAG == 1:
                    #unspread時動作:zaif_ask , coincheck_bidの場合
                    if ca_zb > unspread_Th:
                        unspread_count = unspread_count + 1
                        if unspread_count >= unspread_count_Th:
                            log.info("********************** Unspread OK! ************************")
                            self.TRADE_FLAG = 3
                            Trade_Type = 'ca_zb'
                            Trade_result = ca_zb
                            unspread_count = 0
                else:
                        unspread_count = 0


                if self.TRADE_FLAG ==2:
                    #unspread時動作:coincheck_ask , zaif_bidの場合
                    if za_cb > unspread_Th:
                        unspread_count = unspread_count + 1
                        if unspread_count >= unspread_count_Th:
                            log.info("********************** Unspread OK! ************************")
                            self.TRADE_FLAG = 3
                            Trade_Type = 'za_cb'
                            Trade_result = za_cb
                            unspread_count = 0
                else:
                        unspread_count = 0

            if self.TRADE_FLAG == 3:
                #unspread時動作
                if Trade_Type == 'za_cb':
                    if MODE == "production":
                        #zaifで買って手仕舞いする。
                        self.zaif_api.trade_zaif_ask(btc,zaif_ask)
                        #coincheckで売って手仕舞いする。
                        self.cc_api.trade_coin_bid(btc)
                    else:
                        #zaifで買った価格と数量を出力する。
                        self.zaif_yen_amount = self.zaif_yen_amount - (btc * zaif_ask)
                        self.zaif_btc_amount = self.zaif_btc_amount + btc
                        #coincheckで売った価格と数量を出力する。
                        self.coincheck_yen_amount = self.coincheck_yen_amount + btc * coin_bid
                        self.coincheck_btc_amount = self.coincheck_btc_amount - btc

                    self.close_spread = za_cb

                    log.info('unspread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - coincheck_bid : '+str(za_cb)+' JPY' )
                    slack.Slack.post_message('unspread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - coincheck_bid : '+str(za_cb)+' JPY' )
                    #LINE_BOT('unspread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - coincheck_bid : '+str(za_cb)+' JPY' )

                elif Trade_Type == 'ca_zb':
                    if MODE == "production":
                        #zaifで売って手仕舞いする。
                        self.zaif_api.trade_zaif_bid(btc,zaif_bid) 
                        #coincheckで買って手仕舞いする。
                        self.cc_api.trade_coin_ask(btc,coin_ask)
                    else:
                        #zaifで売った価格と数量を出力する。
                        self.zaif_yen_amount = self.zaif_yen_amount + (btc * zaif_bid)
                        self.zaif_btc_amount = self.zaif_btc_amount - btc
                        #coincheckで買った価格と数量を出力する。
                        self.coincheck_yen_amount = self.coincheck_yen_amount - btc * coin_ask
                        self.coincheck_btc_amount = self.coincheck_btc_amount + btc

                    self.close_spread = ca_zb

                    log.critical('unspread動作実施 : '+str(datetime.datetime.now())+' coincheck_ask - zaif_bid : '+str(ca_zb)+' JPY' )
                    slack.Slack.post_message('unspread動作実施 : '+str(datetime.datetime.now())+' coincheck_ask - zaif_bid : '+str(ca_zb)+' JPY' )
                    #LINE_BOT('unspread動作実施 : '+str(datetime.datetime.now())+' coincheck_ask - zaif_bid : '+str(ca_zb)+' JPY' )
                        
                msg = (str(datetime.datetime.now()) +   ',spread,coin_bid,'+ str(coin_bid) + 
                                                        ',coin_ask,'+ str(coin_ask) + 
                                                        ',zaif_bid,' + str(zaif_bid) + 
                                                        ',zaif_ask,' + str(zaif_ask) + 
                                                        ',Trade_Type,' + str(Trade_Type) + 
                                                        ',Trade_result,' + str(Trade_result) +
                                                        ',open_spread,' + str(self.open_spread) +
                                                        ',close_spread,' + str(self.close_spread) + '\n')

                spreadlog.log_output(self.LOG_PATH,msg)
                #LINE_BOT(msg)
                self.TRADE_FLAG =0
                
            log.info("spread price:" + str(self.open_spread)) 
            log.info("unspread price:" + str(self.close_spread)) 

            if MODE == 'prodeuction':
                balance = self.get_balance()
                log.info("zaif yen-amount:" + "{:,.0f}".format(balance.zaif_jpy) + " " + "btc-amount:" + str(balance.zaif_btc))
                log.info("coincheck yen-amount:" + "{:,.0f}".format(balance.coin_jpy) + " " + "btc-amount:" + str(balance.coin_btc))
                #self.get_balanceに以下の処理を移動する。
                total_yen_amount = balance.zaif_jpy + balance.coin_jpy
                total_btc_amount = balance.zaif_btc + balance.coin_btc
                log.info("total yen-amount:" + "{:,.0f}".format(total_yen_amount) + " " + "total_btc_amount:" + str(total_btc_amount))
                log.info("-------------------------------------------------------------------------------------------")

            else:
                log.info("zaif yen-amount:" + "{:,.0f}".format(self.zaif_yen_amount) + " " + "btc-amount:" + str(self.zaif_btc_amount))
                log.info("coincheck yen-amount:" + "{:,.0f}".format(self.coincheck_yen_amount) + " " + "btc-amount:" + str(self.coincheck_btc_amount))
                total_yen_amount = self.zaif_yen_amount + self.coincheck_yen_amount
                total_btc_amount = self.zaif_btc_amount + self.coincheck_btc_amount
                log.info("total yen-amount:" + "{:,.0f}".format(total_yen_amount) + " " + "total_btc_amount:" + str(total_btc_amount))
                log.info("-------------------------------------------------------------------------------------------")


            time.sleep(freq)

if __name__ == "__main__":

    ZaifCoincheckTrade().run()


"""

・板情報を検索して、発注量の10倍の売り板、買い板がある場合だけ、トレードする。
・価格差1000円程度でトライする。
・デモモードでBTCと円が増減するかシミュレートする。

・spread_thより既定の金額分低い金額をunspread_thに設定するようにする。
・板にエントリロット数の10倍の指値があるときのみエントリする。
・unspread priceとspread priceを修正する。2500固定でよいと思う。

"""
