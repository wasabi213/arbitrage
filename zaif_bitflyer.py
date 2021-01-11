# coding:utf-8

####import設定####
import datetime
import requests
import time
import sys
import csv
import pybitflyer
from zaifapi import ZaifPublicApi,ZaifTradeApi

####初期設定値####
#api設定
BF_access_key = '9GvDQaNwfUb8YRsRdZLaN5' #ビットフライヤーのAPIアクセスキー
BF_secret_key = 'wBkLt/i23jDn10AbZLili1YtV+QNg4Csxkh9bcwr4OE=' #ビットフライヤーのAPIシークレットキー
zaif_access_key = 'bfce8f6f-8677-43e1-9418-4be514e2ce6c' #ザイフのAPIアクセスキー
zaif_secret_key = '522dbe21-6925-45b6-9306-f215a25945cb'  #ザイフのAPIシークレットキー 
#log出力先設定
trade_log_path = r'./zaif_bitflyer.log' #取引実施状況を出力するログファイル。リトライ時ログ確認するため、必須

#初期値
btc = 0.1 #取引量設定（0.006以上推奨※最低取引量は0.005）
freq = 5 #繰り返し周期[sec]
spread_Th = 2500 #「差が十分広がっている」とみなすしきい値
unspread_Th = 250 #「差が十分閉じている」とみなすしきい値
spread_count_Th = 2 #このしきい値以上の回数spread_Thを満たせば取引実施
unspread_count_Th = 2 #このしきい値以上の回数unspread_Thを満たせば逆取引実施
retry_count_Th = 100 #サーバ接続エラーなどでプログラムが停止したとき、このしきい値の回数リトライ実施
retry_freq = 5  #リトライ実施時のwait time[sec]

####関数####
##zaif関係
#zaifでbtc分だけのBitcoinを売る関数
def trade_zaif_bid(btc,zaif_access_key,zaif_secret_key,zaif_bid):
    zaif = ZaifTradeApi(zaif_access_key, zaif_secret_key)
    result = zaif.trade(currency_pair='btc_jpy',action='ask',amount=btc,price=int((zaif_bid-10000)/10)*10)
    return result

#zaifでbtc分だけのBitcoinを買う関数
def trade_zaif_ask(btc,zaif_access_key,zaif_secret_key,zaif_ask):
    #btc分だけのBitcoinをzaifで買います。
    #time.sleep(0.5)
    zaif = ZaifTradeApi(zaif_access_key, zaif_secret_key)
    result = zaif.trade(currency_pair='btc_jpy',action='bid',amount=btc,price=int((zaif_ask+10000)/10)*10)
    return result

##bitflyer関係
#bitflyerのtickerを取得する関数 
def BF_get_ticker():
    #bitflyerFXの価格を取得_publicApiを使用しています。
    bf = pybitflyer.API()
    data_dict = bf.ticker(product_code = "FX_BTC_JPY")
    return data_dict

def trade_bf_bid(api, size, product_code = "FX_BTC_JPY", child_order_type = "MARKET", price = None, minute_to_expire = 10000, time_in_force = "GTC"):
    sell_btc = api.sendchildorder(product_code=product_code, child_order_type=child_order_type, side="SELL",size=size, minute_to_expire=minute_to_expire, time_in_force=time_in_force)
    return sell_btc

def trade_bf_ask(api, size, product_code = "FX_BTC_JPY", child_order_type = "MARKET", price = None, minute_to_expire = 10000, time_in_force = "GTC"):
    buy_btc = api.sendchildorder(product_code=product_code, child_order_type=child_order_type, side="BUY",size=size, minute_to_expire=minute_to_expire, time_in_force=time_in_force)
    return buy_btc

##Log関係
#log出力用関数
def log_output(output_path,msg):
    f = open(output_path,"a",encoding = "UTF-8")
    f.write(msg)
    f.close()

#log入力用関数
def logreader(trade_log_path):
    #ログファイルの最終行から最後に実施した取引を確認する
    f = open(trade_log_path,'r')
    reader = csv.reader(f)
    f.close

    for row in reader:
        lastrow = row

    last_trade_status = lastrow[1]
    last_trade_type = lastrow[11]
    
    if last_trade_status == 'unspread':
        #spread待ち状態
        flag = 0
    else:
        #last_trade_status = 'spread'
        #unspread待ち状態
        if last_trade_type == 'za_bb':
            #spread時:Zaif_ask , BF_bid
            #この逆取引待ち状態からスタートさせる
            flag = 1
        if last_trade_type == 'ba_zb':
            #spread時:Zaif_bid , BF_ask
            #この逆取引待ち状態からスタートさせる             
            flag = 2
    return(flag)

##LINE関係
#LINEにメッセージを送信する関数
def LINE_BOT(msg):
    line_notify_token = ''
    line_notify_api = 'https://notify-api.line.me/api/notify'
    message = msg
    payload = {'message': message}
    headers = {'Authorization': 'Bearer ' + line_notify_token} 
    line_notify = requests.post(line_notify_api, data=payload, headers=headers)
    
    return line_notify

####Programスタート####
#初期化
flag = logreader(trade_log_path) #前回終了時の取引状況の確認
spread_count = 0
unspread_count = 0
api = pybitflyer.API(api_key = BF_access_key, api_secret = BF_secret_key)
print('flag:'+str(flag))

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

#以下繰り返し
while True:

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
        
    #bitflyer_ticker取得
    for i in range(retry_count_Th):
        try:
            bf_data_dict = BF_get_ticker()
        except:
            print('BF_Error:ticker_待機します。 '+str(i)+'回目')
            time.sleep(retry_freq)
        else:
            break
    else:
        print('リトライが全て失敗しました。プログラムを停止します。')
        sys.exit()
    
    #取得したtickerからbid,ask値を読み取る
    bf_bid = bf_data_dict['best_bid']
    bf_ask = bf_data_dict['best_ask']
    zaif_bid = zaif_data_dict['bid']
    zaif_ask = zaif_data_dict['ask']

    #bid値、ask値から損益を計算する
    za_bb = bf_bid - zaif_ask  #zaifで買ってbitflyerで売る
    ba_zb = zaif_bid - bf_ask  #bitflyerで買ってzaifで売る     
    
    if flag ==0:
        status = 'spread待ち'
    else:
        status = 'unspread待ち'
    print(str(datetime.datetime.now())+' '+status+' za_bb:'+str(za_bb)+' ba_zb:'+str(ba_zb))
    
     #Check & Trade
    if flag == 0:
        if za_bb > ba_zb:
            Trade_Type = 'za_bb'
            Trade_result = za_bb
        else:
            Trade_Type = 'ba_zb'
            Trade_result = ba_zb
    
        if Trade_Type == 'za_bb':
            if za_bb > spread_Th:
                spread_count = spread_count + 1
                if spread_count >= spread_count_Th:
                    flag = 1
                    spread_count = 0
            else:
                spread_count = 0
        else:
            if ba_zb > spread_Th:
                spread_count = spread_count + 1
                if spread_count >= spread_count_Th:
                    flag = 2
                    spread_count = 0
            else:
                spread_count = 0
    
        if flag == 0:
            pass
        elif flag == 1 or 2:
            #spread:取引実施
            if flag == 1:
                #zaif_ask , bitflyer_bid
                #zaif_trade = trade_zaif_ask(btc,zaif_access_key,zaif_secret_key,zaif_ask)
                #trade_bf_bid(api=api, size=btc)
                print('spread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - bitflyer_bid : '+str(za_bb)+' JPY' )
                
            elif flag ==2:
                #bitflyer_ask , zaif_bid
                #zaif_trade = trade_zaif_bid(btc,zaif_access_key,zaif_secret_key,zaif_bid)
                #trade_bf_ask(api=api, size=btc)
                print('spread動作実施 : '+str(datetime.datetime.now())+' bitflyer_ask - zaif_bid : '+str(ba_zb)+' JPY' )

            msg = str(datetime.datetime.now()) + ',spread,BF_bid,'+ str(bf_bid) + ',BF_ask,'+ str(bf_ask) + ',zaif_bid,' + str(zaif_bid) + ',zaif_ask,' + str(zaif_ask) + ',Trade_Type,' + str(Trade_Type) + ',Trade_result,' + str(Trade_result) + '\n'
            log_output(trade_log_path,msg)
            #LINE_BOT(msg)
    else:
        if flag == 1:
            #spread時動作:zaif_ask , bitflyer_bidの場合
            if ba_zb > unspread_Th:
                unspread_count = unspread_count + 1
                if unspread_count >= unspread_count_Th:
                    flag = 3
                    Trade_Type = 'ba_zb'
                    Trade_result = ba_zb
                    unspread_count = 0
            else:
                unspread_count = 0
        
        if flag ==2:
            #spread時動作:bitflyer_ask , zaif_bidの場合
            if za_bb > unspread_Th:
                unspread_count = unspread_count + 1
                if unspread_count >= unspread_count_Th:
                    flag = 3
                    Trade_Type = 'za_bb'
                    Trade_result = za_bb
                    unspread_count = 0
            else:
                unspread_count = 0
    
    if flag == 3:
        #unspread時動作
        if Trade_Type == 'za_bb':
            #zaif_trade = trade_zaif_ask(btc,zaif_access_key,zaif_secret_key,zaif_ask)
            #bf_trade = trade_bf_bid(api=api, size=btc)
            print(zaif_trade)
            print(bf_trade)
            print('unspread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - bitflyer_bid : '+str(za_bb)+' JPY' )
                
            
        elif Trade_Type == 'ba_zb':
            #zaif_trade = trade_zaif_bid(btc,zaif_access_key,zaif_secret_key,zaif_bid)
            #bf_trade = trade_bf_ask(api=api, size=btc)
            print(zaif_trade)
            print(bf_trade)
            print('unspread動作実施 : '+str(datetime.datetime.now())+' biflyer_ask - zaif_bid : '+str(ba_zb)+' JPY' )     
            
        msg = str(datetime.datetime.now()) + ',unspread,BF_bid,'+ str(bf_bid) + ',BF_ask,'+ str(bf_ask) + ',zaif_bid,' + str(zaif_bid) + ',zaif_ask,' + str(zaif_ask) + ',Trade_Type,' + str(Trade_Type) + ',Trade_result,' + str(Trade_result) + '\n'
        log_output(trade_log_path,msg)
        #LINE_BOT(msg)
        flag =0
        
    time.sleep(freq)