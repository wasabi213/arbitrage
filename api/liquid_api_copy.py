import json
import requests
import time
import jwt
#import util

class quoineApi:
    def __init__(self):
        self.token_id = '1916874'
        self.api_secret = 'JpFJ9VF1D97QsHzmVxfKS9CAqOXLKPCjjfFnjbGkgYiMnmKlFjLupSXL7RP7xtriNwowt1HYxLi+KmOpA3DT3A=='
        self.api_endpoint = 'https://api.liquid.com'

    def get_api_call(self,path):
        timestamp = str(int(time.time()))
        auth_payload = {
                'path': path,
                'nonce': timestamp,
                'token_id': self.token_id
        }

        #print(auth_payload)


        sign = jwt.encode(auth_payload, self.api_secret, algorithm='HS256')


        print(sign)

        print(self.api_endpoint+path)

        request_data=requests.get(
            self.api_endpoint+path
            ,headers = {
                'X-Quoine-API-Version': '2',
                'X-Quoine-Auth': sign,
                'Content-Type': 'application/json'
            })
        return request_data

    def post_api_call(self,path,body):
        body = json.dumps(body)
        timestamp = str(int(time.time()))
        auth_payload = {
                'path': path,
                'nonce': timestamp,
                'token_id': self.token_id
        }
        sign = jwt.encode(auth_payload, self.api_secret, algorithm='HS256')
        request_data=requests.post(
            self.api_endpoint+path
            ,data = body
            ,headers = {
                'X-Quoine-API-Version': '2',
                'X-Quoine-Auth': sign,
                'Content-Type': 'application/json'
            })
        return request_data

    def get_board(self):
        api = quoineApi()
        result = api.get_api_call('/products/5/price_levels').json()


        #bids = util.util.list_to_pd(result['buy_price_levels'],'qo',False)
        #asks = util.util.list_to_pd(result['sell_price_levels'],'qo',True)
        #return bids,asks

        return result

    def get_balance(self):
        api = quoineApi()
        result = api.get_api_call('/accounts/balance').json()
        data = {}
        for row in result:
            if (row['currency'] == 'JPY'):
                data['jpy_amount'] = round(float(row['balance']), 2)
                data['jpy_available'] = round(float(row['balance']), 2)
            elif (row['currency'] == 'BTC'):
                data['btc_amount'] = round(float(row['balance']), 8)
                data['btc_available'] = round(float(row['balance']), 8)
        return data
    
    def get_accounts(self):
        api = quoineApi()
        result = api.get_api_call('/trading_accounts').json()
        return result

    def get_account(self, account_id):
        api = quoineApi()
        result = api.get_api_call('/trading_accounts/'+account_id).json()
        return result

    def get_open_positions(self):
        api = quoineApi()
        result = api.get_api_call('/trades?status=open').json()
        return result

    def order(self,data):
        api = quoineApi()
        result = api.post_api_call('/orders/',data).json()
        return result


if __name__ == "__main__":


    #print(quoineApi().get_board())
    print(quoineApi().get_balance())

