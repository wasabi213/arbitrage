# LINE関係
##############################
# LINEにメッセージを送信する関数
##############################
def LINE_BOT(msg):
    line_notify_token = ''
    line_notify_api = 'https://notify-api.line.me/api/notify'
    message = msg
    payload = {'message': message}
    headers = {'Authorization': 'Bearer ' + line_notify_token}
    line_notify = requests.post(line_notify_api, data=payload, headers=headers)

    return line_notify
