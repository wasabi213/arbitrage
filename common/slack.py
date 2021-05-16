# -*- coding: utf8 -*-

from datetime import datetime
import requests
import json

import configparser
inifile = configparser.ConfigParser()
CONFIG_FILE = '../config/zaif_coincheck_config.ini'
inifile.read(CONFIG_FILE, 'UTF-8')

#
# Slackに投稿する。
#


class Slack:

    # Slackに送信する。
    @staticmethod
    def post_message(text):
        webhook_url = inifile.get('slack', 'post_url')
        botname = 'arbitrage-bot'

        slack_text = "システム名:zaif coincheck arbitrage" + \
            "\n" + "メッセージ送信時刻:" + str(datetime.now()) + "\n"
        slack_text += text
        requests.post(
            webhook_url,
            data=json.dumps(
                {"text": slack_text,
                 "username": botname,
                 "icon_emoji": ":python:"}))


if __name__ == '__main__':

    Slack().post_message("これはテストです")
