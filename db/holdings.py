# db/holdings.py

from utils.balance import balance

def get_holding_symbols():
    return list(balance["holdings"].keys())

def get_holding_data(symbol):
    return balance["holdings"].get(symbol)
