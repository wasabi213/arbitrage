import os
import codecs
import configparser


##Log関係
##############
#log出力用関数
##############
def log_output(output_path,msg):

    CONFIG_FILE = '../config/zaif_coincheck_config.ini'
    conf = configparser.ConfigParser() 
    conf.readfp(codecs.open(CONFIG_FILE,"r","utf8"))

    #APIキーの取得
    OUTPUT_PATH = conf.get("path","trade_log_path")

    f = open(output_path,"a",encoding = "UTF-8")
    f.write(msg)
    f.close()

#def createLog():

