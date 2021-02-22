# coding:utf-8
####import設定####
import datetime
import requests
import time
import sys
import hmac
import hashlib
import json
import csv
import ccxt
####初期設定値####
#api設定
coin_access_key = '' #ｺｲﾝﾁｪｯｸのAPIｱｸｾｽｷｰ
coin_secret_key = '' #ｺｲﾝﾁｪｯｸのAPIｼｰｸﾚｯﾄｷｰ
quoinex = ccxt.quoinex({'apiKey': '','secret': '',})
#log出力先設定
trade_log_path = r'' #取引実施状況を出力するログファイル。リトライ時ログ確認するため、必須
#初期値
btc = 0.1 #取引量設定（0.006以上推奨※最低取引量は0.005）
freq = 5 #繰り返し周期[sec]
spread_Th = 3000 #「差が十分広がっている」とみなすしきい値
unspread_Th = 0 #「差が十分閉じている」とみなすしきい値
spread_count_Th = 2 #このしきい値以上の回数spread_Thを満たせば取引実施
unspread_count_Th = 2 #このしきい値以上の回数unspread_Thを満たせば逆取引実施
retry_count_Th = 100 #サーバ接続エラーなどでプログラムが停止したとき、このしきい値の回数リトライ実施
retry_freq = 5  #リトライ実施時のwait time[sec]
####関数####
##coincheck関係
#coincheckのtickerを取得する関数(publicApiを使用)
def coin_get_ticker():
   url = 'https://coincheck.jp/api/ticker'
   return requests.get(url).text
#coincheckのPrivateAPIﾘｸｴｽﾄ送信関数
def ccPrivateApi(i_path, i_nonce, i_params=None, i_method="get"):
 API_URL="https://coincheck.com"
 headers={'ACCESS-KEY':coin_access_key, 
          'ACCESS-NONCE':str(i_nonce), 
          'Content-Type': 'application/json'}
 s = hmac.new(bytearray(coin_secret_key.encode('utf-8')), digestmod=hashlib.sha256)
 
 if i_params is None:
   w = str(i_nonce) + API_URL + i_path
   s.update(w.encode('utf-8'))
   headers['ACCESS-SIGNATURE'] = s.hexdigest()
   if i_method == "delete":
     return requests.delete(API_URL+i_path, headers=headers)
   else:
     return requests.get(API_URL+i_path, headers=headers)
 else:    
   body = json.dumps(i_params);
   w = str(i_nonce) + API_URL + i_path + body
   s.update(w.encode('utf-8'))
   headers['ACCESS-SIGNATURE'] = s.hexdigest()
   return requests.post(API_URL+i_path, data=body, headers=headers)
#coincheckでbtc分のBitcoinを売る関数
def trade_coin_bid(btc):
    #order_type : market_sell : 成行注文　現物取引　売り
   nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100
   c = ccPrivateApi("/api/exchange/orders",nonce,
                    {"pair":"btc_jpy",
                     "order_type":"market_sell",
                     "amount":btc})
   r = c.json()
   return r
#coincheckでbtc分のBitcoinを買う関数
def trade_coin_ask(btc,coin_ask):
    #order_type : market_buy : 成行注文　現物取引　買い
   #買いの成行注文をする場合は、円（JPY）でのmarket_buy_amountの指定必須
   nonce = int((datetime.datetime.today() - datetime.datetime(2017,1,1)).total_seconds()) * 100
   c = ccPrivateApi("/api/exchange/orders",nonce,
                    {"pair":"btc_jpy",
                     "order_type":"market_buy",
                     "market_buy_amount":int(btc*coin_ask)})
   r = c.json()
   return r
##quoinex関係
#quoinexのtickerを取得する関数 
def qe_get_ticker():
   quoinex = ccxt.quoinex()
   ticker = quoinex.fetch_ticker('BTC/JPY')
   return ticker
#quoinexでsize分のBitcoinを売る関数
def trade_quoinex_bid(size):
   result = quoinex.create_order('BTC/JPY', type='market', side='sell', amount=size)
   return result
#quoinexでsize分のBitcoinを買う関数
def trade_quoinex_ask(size):
   result = quoinex.create_order('BTC/JPY', type='market', side='buy', amount=size)
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
        #unspread待ち状態        if last_trade_type == 'ca_qb':
           #spread時:coin_ask , Quoinex_bid
            #この逆取引待ち状態からスタートさせる            flag = 1
       if last_trade_type == 'qa_cb':
           #spread時:coin_bid , Quoinex_ask
            #この逆取引待ち状態からスタートさせる            flag = 2
   return(flag)
####Programスタート####
#初期化
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
    #coincheck_ticker取得    for i in range(retry_count_Th):
       try:
           coin_data_dict = json.loads(coin_get_ticker())
       except:
           print('coin_Error:ticker_待機します。 '+str(i)+'回目')
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
   coin_bid = coin_data_dict['bid']
   coin_ask = coin_data_dict['ask']
   qe_bid = qe_data_dict['bid']
   qe_ask = qe_data_dict['ask']
   
   #bid値、ask値から損益を計算する
   ca_qb = qe_bid - coin_ask #coincheckで買ってquoinexで売る
   qa_cb = coin_bid - qe_ask #quoinexで買ってcoincheckで売る
   
   if flag ==0:
       status = 'spread待ち'
   else:
       status = 'unspread待ち'
       
   print(str(datetime.datetime.now())+' '+status+' ca_qb:'+str(round(ca_qb,3))+' qa_cb:'+str(round(qa_cb,3)))
   
    #Check & Trade
   if flag == 0:
       if ca_qb > qa_cb:
           Trade_Type = 'ca_qb'
           Trade_result = ca_qb
       else:
           Trade_Type = 'qa_cb'
           Trade_result = qa_cb
           
       if Trade_Type == 'ca_qb':
           if ca_qb > spread_Th:
               spread_count = spread_count + 1
               if spread_count >= spread_count_Th:
                   flag = 1
                   spread_count = 0
           else:
               spread_count = 0
       else:
           if qa_cb > spread_Th:
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
                #coincheck_ask , quoinex_bid
               try:
                   qe_trade = trade_quoinex_bid(btc)
                   coin_trade = trade_coin_ask(btc,coin_ask)
                   print('spread動作実施 : '+str(datetime.datetime.now())+' coin_ask - quoinex_bid : '+str(ca_qb)+' JPY' )
               except:
                   print('spread動作エラー')
                   print(qe_trade)
                   print(coin_trade)

                   sys.exit()
               
           elif flag ==2:
               #quoinex_ask , coincheck_bid
               try:
                   qe_trade = trade_quoinex_ask(btc)
                   coin_trade = trade_coin_bid(btc)
                   print('spread動作実施 : '+str(datetime.datetime.now())+' quoinex_ask - coin_bid : '+str(qa_cb)+' JPY' )
               except:
                    print('spread動作エラー')
                    print(qe_trade)
                    print(coin_trade)
                    sys.exit()
               
           msg = str(datetime.datetime.now()) + ',spread,qe_bid,'+ str(qe_bid) + ',qe_ask,'+ str(qe_ask) + ',coin_bid,' + str(coin_bid) + ',coin_ask,' + str(coin_ask) + ',Trade_Type,' + str(Trade_Type) + ',Trade_result,' + str(Trade_result) + '\n'
           log_output(trade_log_path,msg)
   else:
       if flag == 1:
           #spread時動作:coin_ask , quoinex_bidの場合
           if qa_cb > unspread_Th:
               unspread_count = unspread_count + 1
               if unspread_count >= unspread_count_Th:
                   flag = 3
                   Trade_Type = 'qa_cb'
                   Trade_result = qa_cb
                   unspread_count = 0
           else:
               unspread_count = 0
       if flag ==2:
           #spread時動作:quoinex_ask , coin_bidの場合
           if ca_qb > unspread_Th:
               unspread_count = unspread_count + 1
               if unspread_count >= unspread_count_Th:
                   flag = 3
                   Trade_Type = 'ca_qb'
                   Trade_result = ca_qb
                   unspread_count = 0
           else:
               unspread_count = 0
   if flag == 3:
        #unspread時動作        if Trade_Type == 'ca_qb':
           try:
               qe_trade = trade_quoinex_bid(btc)
               coin_trade = trade_coin_ask(btc,coin_ask)
               print('unspread動作実施 : '+str(datetime.datetime.now())+' coin_ask - quoinex_bid : '+str(ca_qb)+' JPY' )
           except:
               print('unspread動作エラー')
               print(qe_trade)
               print(coin_trade)
               sys.exit()
       
       elif Trade_Type == 'qa_cb':
           try:
               qe_trade = trade_quoinex_ask(btc)
               coin_trade = trade_coin_bid(btc)
               print('unspread動作実施 : '+str(datetime.datetime.now())+' quoinex_ask - coin_bid : '+str(qa_cb)+' JPY' )
           except:
               print('unspread動作エラー')
               print(qe_trade)
               print(coin_trade)
               sys.exit()
        
       msg = str(datetime.datetime.now()) + ',unspread,qe_bid,'+ str(qe_bid) + ',qe_ask,'+ str(qe_ask) + ',coin_bid,' + str(coin_bid) + ',coin_ask,' + str(coin_ask) + ',Trade_Type,' + str(Trade_Type) + ',Trade_result,' + str(Trade_result) + '\n'
       log_output(trade_log_path,msg)
       flag =0
       
   time.sleep(freq)