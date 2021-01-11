# coding:utf-8
####import設定####
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
from common import log


CONFIG_FILE = '../config/zaif_coincheck_config.ini'
MODE = "test"


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
        print(self.LOG_PATH)
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
                print('CoinCheckでエラーが発生した履歴があります。プログラムスタートさせません。')
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
                    print('前回のspreadが記録されていません。')
                    sys.exit()

                self.open_spread = lastrow[15]
                self.close_spread = lastrow[16]

        return(self.TRADE_FLAG)

    #スタート時のパラメータ表示
    def showParameter(self):
        print('flag:'+str(self.TRADE_FLAG))
        #初期値の表示
        print('設定取引量：'+ str(btc) + 'btc')
        print('繰り返し周期：'+ str(freq) + 'sec')
        print('リトライ繰り返し周期：'+ str(retry_freq) + 'sec')
        print('spreadしきい値：'+str(spread_Th)+ 'yen')
        print('unspreadしきい値：'+str(unspread_Th)+ 'yen')
        print('spreadカウントしきい値:'+str(spread_count_Th)+'回')
        print('unspreadカウントしきい値:'+str(unspread_count_Th)+'回')
        print('リトライカウントしきい値:'+str(retry_count_Th)+'回')
        print('ArbitrageProgram を開始します : '+str(datetime.datetime.now()))

    def getBrokerTicker(self):
        #zaif_ticker取得
        for i in range(retry_count_Th):
            try:
                zaif = ZaifPublicApi()
                zaif_data_dict = zaif.ticker('btc_jpy')
            except:
                print('zaif_Error:ticker_待機します。 '+str(i)+'回目')
                time.sleep(retry_freq)
            else:
                break
        else:
            print('リトライが全て失敗しました。プログラムを停止します。')
            sys.exit()
            
        #coincheck_ticker取得
        for i in range(retry_count_Th):
            try:
                coin_data_dict = json.loads(self.cc_api.coin_get_ticker())
            except:
                print('coin_Error:ticker_待機します。 '+str(i)+'回目')
                time.sleep(retry_freq)
            else:
                break
        else:
            print('リトライが全て失敗しました。プログラムを停止します。')
            sys.exit()

    #フラグの状態を取得する。spread待ちか、unspread待ちか。
    def getStatus(self):
        if self.TRADE_FLAG == 0:
            status = 'spread待ち'
        else:
            status = 'unspread待ち'

        return status

    def printBrokerBoardDetail(self,coin_bid,coin_ask,zaif_bid,zaif_ask,coin_bid_lot,coin_ask_lot,zaif_bid_lot,zaif_ask_lot,za_cb,ca_zb):
        tm_str = str(datetime.datetime.now())
        print(tm_str + " zaif_ask:" + "{:,.0f}".format(zaif_ask))
        print(tm_str + " zaif_bid:" + "{:,.0f}".format(zaif_bid))
        print(tm_str + " coin_ask:" + "{:,.0f}".format(coin_ask))
        print(tm_str + " coin_bid:" + "{:,.0f}".format(coin_bid))
        print(tm_str + " za_cb: coin_bid - zaif_ask = " + "{:,.0f}".format(za_cb))
        print(tm_str + " ca_zb: zaif_bid - coin_ask = " + "{:,.0f}".format(ca_zb))

        print(tm_str + " coincheck " + "BUY:" + "{:,.0f}".format(coin_bid) + "," + str(coin_bid_lot) + 
                " SELL:" + "{:,.0f}".format(coin_ask) + "," + str(coin_ask_lot))
        print(tm_str + " zaif " + "BUY:" + "{:,.0f}".format(zaif_bid) + "," + str(zaif_bid_lot) + 
                " SELL:" + "{:,.0f}".format(zaif_ask) + "," + str(zaif_ask_lot))
        print(tm_str + ' ' + self.getStatus() + ' za_cb:' + str(za_cb) + ' ca_zb:' + str(ca_zb))


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

            #板情報からbidとaskを取り出す
            coin_bid = float(self.cc_api.coincheck_get_board_bid(coincheck_result))
            coin_ask = float(self.cc_api.coincheck_get_board_ask(coincheck_result))
            zaif_bid = float(self.zaif_api.zaif_get_board_bid(zaif_result))
            zaif_ask = float(self.zaif_api.zaif_get_board_ask(zaif_result))

            #lotを取得する。
            coin_bid_lot = float(self.cc_api.coincheck_get_board_bid_lot(coincheck_result))
            coin_ask_lot = float(self.cc_api.coincheck_get_board_ask_lot(coincheck_result))
            zaif_bid_lot = float(self.zaif_api.zaif_get_board_bid_lot(zaif_result))
            zaif_ask_lot = float(self.zaif_api.zaif_get_board_ask_lot(zaif_result))

            #bid値、ask値から損益を計算する
            za_cb = coin_bid - zaif_ask  #zaifで買ってcoincheckで売る
            ca_zb = zaif_bid - coin_ask  #coincheckで買ってzaifで売る  

            #板の詳細情報を画面に表示する。
            self.printBrokerBoardDetail(coin_bid,coin_ask,zaif_bid,zaif_ask,coin_bid_lot,coin_ask_lot,zaif_bid_lot,zaif_ask_lot,za_cb,ca_zb)            

            ########################################################################    
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
                        print("**********************\nSpread OK!\n************************")
                        spread_count = spread_count + 1

                        #spreadが2回連続でしきい値を超えたら、フラグを設定する。
                        if spread_count >= spread_count_Th:
                            
                            #板に設定された倍率以上の指値が入っている場合フラグを設定する。
                            if zaif_ask_lot > btc * entry_rate and coin_bid_lot > btc * entry_rate:
                                print("Lot OK!")
                                self.TRADE_FLAG = 1
                                spread_count = 0
                    else:
                        spread_count = 0
                else:
                    if ca_zb > spread_Th:
                        print("**********************\nSpread OK!\n************************")
                        spread_count = spread_count + 1

                        #spreadが2回連続でしきい値を超えたら、フラグを設定する。
                        if spread_count >= spread_count_Th:
                            #板に設定された倍率以上の指値が入っている場合フラグを設定する。
                            if coin_ask_lot > btc * entry_rate and zaif_bid_lot > btc * entry_rate:                       
                                print("Lot OK!")
                                self.TRADE_FLAG = 2
                                spread_count = 0
                    else:
                        spread_count = 0

            ########################################################################    



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
                        print('spread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - coincheck_bid : '+str(za_cb)+' JPY' )

    
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
                        print('spread動作実施 : '+str(datetime.datetime.now())+' coincheck_ask - zaif_bid : '+str(ca_zb)+' JPY' )
                    
                    msg = (str(datetime.datetime.now()) +   ',spread,coin_bid,'+ str(coin_bid) + 
                                                            ',coin_ask,'+ str(coin_ask) + 
                                                            ',zaif_bid,' + str(zaif_bid) + 
                                                            ',zaif_ask,' + str(zaif_ask) + 
                                                            ',Trade_Type,' + str(Trade_Type) + 
                                                            ',Trade_result,' + str(Trade_result) +
                                                            ',open_spread,' + str(self.open_spread) +
                                                            ',close_spread,' + str(self.close_spread) + '\n')

                    log.log_output(self.LOG_PATH,msg)
                    #LINE_BOT(msg)
            else:
                if self.TRADE_FLAG == 1:
                    #unspread時動作:zaif_ask , coincheck_bidの場合
                    if ca_zb > unspread_Th:
                        unspread_count = unspread_count + 1
                        if unspread_count >= unspread_count_Th:
                            print("**********************\nUnspread OK!\n************************")

                            #板に設定された倍率以上の指値が入っている場合フラグを設定する。
                            if coin_ask_lot > btc * entry_rate and zaif_bid_lot > btc * entry_rate:
                                print("Unspread Lot OK!")
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
                            print("**********************\nUnspread OK!\n************************")
                            #板に設定された倍率以上の指値が入っている場合フラグを設定する。
                            if zaif_ask_lot > btc * entry_rate and coin_bid_lot > btc * entry_rate:
                                print("Unspread Lot OK!")

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
                        self.zaif_api.trade_zaif_ask(btc,zaif_access_key,zaif_secret_key,zaif_ask)
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

                    print('unspread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - coincheck_bid : '+str(za_cb)+' JPY' )
                    #LINE_BOT('unspread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - coincheck_bid : '+str(za_cb)+' JPY' )

                elif Trade_Type == 'ca_zb':
                    if MODE == "production":
                        #zaifで売って手仕舞いする。
                        self.zaif_api.trade_zaif_bid(btc,zaif_access_key,zaif_secret_key,zaif_bid) 
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

                    print('unspread動作実施 : '+str(datetime.datetime.now())+' coincheck_ask - zaif_bid : '+str(ca_zb)+' JPY' )
                    #LINE_BOT('unspread動作実施 : '+str(datetime.datetime.now())+' coincheck_ask - zaif_bid : '+str(ca_zb)+' JPY' )
                        
                msg = (str(datetime.datetime.now()) +   ',spread,coin_bid,'+ str(coin_bid) + 
                                                        ',coin_ask,'+ str(coin_ask) + 
                                                        ',zaif_bid,' + str(zaif_bid) + 
                                                        ',zaif_ask,' + str(zaif_ask) + 
                                                        ',Trade_Type,' + str(Trade_Type) + 
                                                        ',Trade_result,' + str(Trade_result) +
                                                        ',open_spread,' + str(self.open_spread) +
                                                        ',close_spread,' + str(self.close_spread) + '\n')

                log.log_output(self.LOG_PATH,msg)
                #LINE_BOT(msg)
                self.TRADE_FLAG =0
                
            print("spread price:" + str(self.open_spread)) 
            print("unspread price:" + str(self.close_spread)) 
            print("zaif yen-amount:" + "{:,.0f}".format(self.zaif_yen_amount) + " " + "btc-amount:" + str(self.zaif_btc_amount))
            print("coincheck yen-amount:" + "{:,.0f}".format(self.coincheck_yen_amount) + " " + "btc-amount:" + str(self.coincheck_btc_amount))

            total_yen_amount = self.zaif_yen_amount + self.coincheck_yen_amount
            total_btc_amount = self.zaif_btc_amount + self.coincheck_btc_amount
            print("total yen-amount:" + "{:,.0f}".format(total_yen_amount) + " " + "total_btc_amount:" + str(total_btc_amount))
            print("-------------------------------------------------------------------------------------------")
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
