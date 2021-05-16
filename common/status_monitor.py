import os
import pathlib
import json


class StatusMonitor:

    def __init__(self, primary, secondary):
        self.primary_broker = primary
        self.secondary_broker = secondary
        self.monitor_file_name = self.primary_broker + \
            '_' + self.secondary_broker + '_monitor.log'
        self.monitor_path = '../trade_log/' + self.monitor_file_name

        self.createMonitorFile(self.monitor_path)

    def createMonitorFile(self, log_path):
        if os.path.exists(log_path):
            return
        else:
            path = pathlib.Path(self.monitor_path)
            path.touch()

    def setInfo(self, info):
        f = open(self.monitor_path, 'w')
        json.dump(info, f)
        f.close()

    # Zaif-Coincheckの組み合わせはこのメソッドを使う。
    def setInfoforZaifCoincheck(self, info):

        total_jpy = "{:.0f}".format(
            float(info["balance"]["zaif_jpy"]) + float(info["balance"]["coin_jpy"]))
        total_btc = "{:.3f}".format(
            float(info["balance"]["zaif_btc"]) + float(info["balance"]["coin_btc"]))
        btc_price = float(info["board"]["zaif_bid"][0]) if float(info["board"]["zaif_bid"][0]) < float(
            info["board"]["coin_bid"][0]) else float(info["board"]["coin_bid"][0])
        total_btc_price = "{:.0f}".format(float(total_btc) * btc_price)
        total_asset_price = int(total_btc_price) + int(total_jpy)

        data = {
            "primary": self.primary_broker,
            "secondary": self.secondary_broker,
            "profit": "{:.0f}".format(float(info["add_info"]["profit"])),
            "primary_jpy": "{:.0f}".format(float(info["balance"]["zaif_jpy"])),
            "primary_btc": info["balance"]["zaif_btc"],
            "secondary_jpy": "{:.0f}".format(float(info["balance"]["coin_jpy"])),
            "secondary_btc": info["balance"]["coin_btc"],
            "total_jpy": total_jpy,
            "total_btc": total_btc,
            "total_btc_price": total_btc_price,
            "total_asset_price": total_asset_price,
            "mode": info['add_info']['mode'],
            "primary_over_threshold_time": info['add_info']['primary_over_threshold_time'],
            "secondary_over_threshold_time": info['add_info']['secondary_over_threshold_time'],
            "entry_rate": info['add_info']['entry_rate'],
            "reverse_side": str(info['add_info']['reverse_side']),
            "unbalance": str(info['add_info']['unbalance']),
            "btc_start_amount": info['add_info']['btc_start_amount'],
            "primary_latest_buy": info['add_info']['primary_latest_buy'],
            "primary_latest_buy_lot": info['add_info']['primary_latest_buy_lot'],
            "primary_latest_buy_time": info['add_info']['primary_latest_buy_time'],
            "primary_latest_sell": info['add_info']['primary_latest_sell'],
            "primary_latest_sell_lot": info['add_info']['primary_latest_sell_lot'],
            "primary_latset_sell_time": info['add_info']['primary_latest_sell_time'],
            "secondary_latest_buy": info['add_info']['secondary_latest_buy'],
            "secondary_latest_buy_lot": info['add_info']['secondary_latest_buy_lot'],
            "secondary_latset_buy_time": info['add_info']['secondary_latest_buy_time'],
            "secondary_latest_sell": info['add_info']['secondary_latest_sell'],
            "secondary_latest_sell_lot": info['add_info']['secondary_latest_sell_lot'],
            "secondary_latset_sell_time": info['add_info']['secondary_latest_sell_time'],
            "primary_ask": info["board"]["zaif_ask"][0],
            "primary_ask_lot": info["board"]["zaif_ask_lot"][0],
            "primary_bid": info["board"]["zaif_bid"][0],
            "primary_bid_lot": info["board"]["zaif_bid_lot"][0],
            "secondary_ask": info["board"]["coin_ask"][0],
            "secondary_ask_lot": info["board"]["coin_ask_lot"][0],
            "secondary_bid": info["board"]["coin_bid"][0],
            "secondary_bid_lot": info["board"]["coin_bid_lot"][0],
            "primary_safety_ask": info['board']['zaif_tradable_ask_price'],
            "primary_safety_ask_lot": info['board']['zaif_tradable_ask_lot_total'],
            "primary_safety_bid": info['board']['zaif_tradable_bid_price'],
            "primary_safety_bid_lot": info['board']['zaif_tradable_bid_lot_total'],
            "secondary_safety_ask": info['board']['coin_tradable_ask_price'],
            "secondary_safety_ask_lot": info['board']['coin_tradable_ask_lot_total'],
            "secondary_safety_bid": info['board']['coin_tradable_bid_price'],
            "secondary_safety_bid_lot": info['board']['coin_tradable_bid_lot_total'],
            "pbsa_gap": info['board']['zaif_bid'][0] - info['board']['coin_ask'][0],
            "sbpa_gap": info['board']['coin_bid'][0] - info['board']['zaif_ask'][0],
            "pbsa_safety_gap": info['board']['zaif_tradable_bid_price'] - info['board']['coin_tradable_ask_price'],
            "sbpa_safety_gap": info['board']['coin_tradable_bid_price'] - info['board']['zaif_tradable_ask_price'],
            "entry_spread": info['add_info']['entry_spread'],
            "reverse_spread": info['add_info']['reverse_spread'],
        }
        self.setInfo(data)
