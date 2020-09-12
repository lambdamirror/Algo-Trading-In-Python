# -*- coding: utf-8 -*-
"""
Created on Sat Mar 24 00:16:07 2020

@author: tranl
"""

import pandas as pd
import sys

### Ultility functions  
def barstr(text, symbol='#', length=100, space_size=5):
    '''
    Returns a marked line in the form #### < str > ###
    '''
    bar_size = int((length-len(text))/2)
    bar = ''.join([symbol]*(bar_size-space_size))
    space = ''.join([' ']*space_size)
    return '{:<}{}{}{}{:>}'.format(bar, space, text, space, bar)
  
def print_(s, file):
    '''
    Prints a string s into file
    '''
    with open(file, "a+") as f: 
        f.write('\n' + str(s)) 
    f.close()
    print(s)

def orderstr(order):
    '''
    Returns string representation of the order response from Binance
    '''
    try:
        s = 'Market response: '
        s += 'Id:' + str(order['orderId']) + ' status:' + str(order['status']) + ' side:' + str(order['side']) + ' type:' + str(order['type']) + ' quantity:' + str(order['origQty'])
        if order['type']=='LIMIT':
            s += ' price:' + str(order['price']) + ' TIF:' + str(order['timeInForce'])
        elif order['type']=='TRAILING_STOP_MARKET':
            s += ' price:' + str(order['activatePrice']) + ' cbRate:' + str(order['priceRate'])
        s += ' time:' + pd.to_datetime(order['updateTime'], unit='ms').strftime("%y-%m-%d %H:%M:%S")
        return s
    except Exception:
        s = "Invalid order response from the Market"
        return s
        
def timestr(dateTime: int, end='f'):
    '''
    Returns string representation for an interger time
    '''
    if end=='m': s = pd.to_datetime(dateTime, unit='ms').strftime("%y-%m-%d %H:%M")
    elif end=='s': s = pd.to_datetime(dateTime, unit='ms').strftime("%y-%m-%d %H:%M:%S")
    elif end=='f': s = pd.to_datetime(dateTime, unit='ms').strftime("%y-%m-%d %H:%M:%S:%f")[:-3]
    return s