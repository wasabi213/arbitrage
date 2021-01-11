# coding:utf-8
####import設定####
import datetime
import requests
import time
import sys
import csv
import ccxt
from zaifapi import ZaifPublicApi,ZaifTradeApi
####初期設定値####
#api設定
zaif_access_key = '' #ザイフのAPIアクセスキー
zaif_secret_key = ''  #ザイフのAPIシークレットキー quoinex = ccxt.quoinex({
   'apiKey': '',     # quoinexのAPIアクセスキー
   'secret': '',  # quoinexのAPIシークレットキー
})
#log出力先設定
trade_log_path = r'' #取引実施状況を出力するログファイル。リトライ時ログ確認するため、必須
#初期値
btc = 0.1 #取引量設定（0.006以上推奨※最低取引量は0.005）
freq = 5 #繰り返し周期[sec]
spread_Th = 2000 #「差が十分広がっている」とみなすしきい値
unspread_Th = 200 #「差が十分閉じている」とみなすしきい値
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
##quoinex関係
#quoinexのtickerを取得する関数 
def qe_get_ticker():
   quoinex = ccxt.quoinex()
   ticker = quoinex.fetch_ticker('BTC/JPY')
   return ticker
def trade_quoinex_ask(size):
   result = quoinex.create_order('BTC/JPY', type='market', side='buy', amount=size)
   return result
def trade_quoinex_bid(size):
   result = quoinex.create_order('BTC/JPY', type='market', side='sell', amount=size)
   return result
##Log関係
#log出力用関数
def log_output(output_path,msg):
   f = open(output_path,"a",encoding = "UTF-8")
   f.write(msg)
   f.close()
#log入力用関数
def logreader(trade_log_path):
    #ログファイルの最終行から最後に実施した取引を確認する    f = open(trade_log_path,'r')
   reader = csv.reader(f)
   f.close
   for row in reader:
       lastrow = row
   last_trade_status = lastrow[1]
   last_trade_type = lastrow[11]
   
   if last_trade_status == 'unspread':
        #spread待ち状態        flag = 0
   else:
        #last_trade_status = 'spread'
        #unspread待ち状態        if last_trade_type == 'za_qb':
           #spread時:Zaif_ask , Quoinex_bid
            #この逆取引待ち状態からスタートさせる            flag = 1
       if last_trade_type == 'qa_zb':
           #spread時:Zaif_bid , Quoinex_ask
            #この逆取引待ち状態からスタートさせる            flag = 2
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
#flag = 0
flag = logreader(trade_log_path) #前回終了時の取引状況の確認
spread_count = 0
unspread_count = 0
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
    #zaif_ticker取得    for i in range(retry_count_Th):
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
       
   #quoinex_ticker取得
   for i in range(retry_count_Th):
       try:
           qe_data_dict = qe_get_ticker()
       except:
           print('quoinex_Error:ticker_待機します。 '+str(i)+'回目')
           time.sleep(retry_freq)
       else:
           break
   else:
       print('リトライが全て失敗しました。プログラムを停止します。')
       sys.exit()
   
   #取得したtickerからbid,ask値を読み取る
   qe_bid = qe_data_dict['bid']
   qe_ask = qe_data_dict['ask']
   zaif_bid = zaif_data_dict['bid']
   zaif_ask = zaif_data_dict['ask']
   #bid値、ask値から損益を計算する
   za_qb = qe_bid - zaif_ask #zaifで買ってquoinexで売る
   qa_zb = zaif_bid - qe_ask #quoinexで買ってzaifで売る
   
   
   if flag ==0:
       status = 'spread待ち'
   else:
       status = 'unspread待ち'
   print(str(datetime.datetime.now())+' '+status+' za_qb:'+str(za_qb)+' qa_zb:'+str(qa_zb))
   
    #Check & Trade
   if flag == 0:
       if za_qb > qa_zb:
           Trade_Type = 'za_qb'
           Trade_result = za_qb
       else:
           Trade_Type = 'qa_zb'
           Trade_result = qa_zb
   
       if Trade_Type == 'za_qb':
           if za_qb > spread_Th:
               spread_count = spread_count + 1
               if spread_count >= spread_count_Th:
                   flag = 1
                   spread_count = 0
           else:
               spread_count = 0
       else:
           if qa_zb > spread_Th:
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
                #zaif_ask , quoinex_bid
               zaif_trade = trade_zaif_ask(btc,zaif_access_key,zaif_secret_key,zaif_ask)
               qe_trade = trade_quoinex_bid(btc)
               print('spread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - quoinex_bid : '+str(za_qb)+' JPY' )
               
           elif flag ==2:
               #quoinex_ask , zaif_bid
               zaif_trade = trade_zaif_bid(btc,zaif_access_key,zaif_secret_key,zaif_bid)
               qe_trade = trade_quoinex_ask(btc)
               print('spread動作実施 : '+str(datetime.datetime.now())+' quoinex_ask - zaif_bid : '+str(qa_zb)+' JPY' )
           msg = str(datetime.datetime.now()) + ',spread,qe_bid,'+ str(qe_bid) + ',qe_ask,'+ str(qe_ask) + ',zaif_bid,' + str(zaif_bid) + ',zaif_ask,' + str(zaif_ask) + ',Trade_Type,' + str(Trade_Type) + ',Trade_result,' + str(Trade_result) + '\n'
           log_output(trade_log_path,msg)
           #LINE_BOT(msg)
   else:
       if flag == 1:
           #spread時動作:zaif_ask , quoinex_bidの場合
           if qa_zb > unspread_Th:
               unspread_count = unspread_count + 1
               if unspread_count >= unspread_count_Th:
                   flag = 3
                   Trade_Type = 'qa_zb'
                   Trade_result = qa_zb
                   unspread_count = 0
           else:
               unspread_count = 0
       
       if flag ==2:
           #spread時動作:quoinex_ask , zaif_bidの場合
           if za_qb > unspread_Th:
               unspread_count = unspread_count + 1
               if unspread_count >= unspread_count_Th:
                   flag = 3
                   Trade_Type = 'za_qb'
                   Trade_result = za_qb
                   unspread_count = 0
           else:
               unspread_count = 0
   
   if flag == 3:
        #unspread時動作        if Trade_Type == 'za_qb':
           zaif_trade = trade_zaif_ask(btc,zaif_access_key,zaif_secret_key,zaif_ask)
           qe_trade = trade_quoinex_bid(btc)
           print('unspread動作実施 : '+str(datetime.datetime.now())+' zaif_ask - quoinex_bid : '+str(za_qb)+' JPY' )
               
           
       elif Trade_Type == 'qa_zb':
           zaif_trade = trade_zaif_bid(btc,zaif_access_key,zaif_secret_key,zaif_bid)
           qe_trade = trade_quoinex_ask(btc)
           print('unspread動作実施 : '+str(datetime.datetime.now())+' quoinex_ask - zaif_bid : '+str(qa_zb)+' JPY' )     
           
       msg = str(datetime.datetime.now()) + ',unspread,qe_bid,'+ str(qe_bid) + ',qe_ask,'+ str(qe_ask) + ',zaif_bid,' + str(zaif_bid) + ',zaif_ask,' + str(zaif_ask) + ',Trade_Type,' + str(Trade_Type) + ',Trade_result,' + str(Trade_result) + '\n'
       log_output(trade_log_path,msg)
       #LINE_BOT(msg)
       flag =0
       
   time.sleep(freq)