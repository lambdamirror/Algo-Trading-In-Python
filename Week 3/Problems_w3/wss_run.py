# -*- coding: utf-8 -*-
"""
Created on Sat Mar 24 00:16:07 2020

@author: tranl
"""
import time, os
import numpy as np
import pandas as pd
import websocket
import threading
import json

from binancepy import Client
from ultilities import timestr, barstr

### wss functions
def on_message(ws, message):
    '''
    Control the message received from 
    '''
    mess = json.loads(message)
    if mess['e'] == 'kline':
        kln = mess['k']
        if kln['x'] is True:
            symbol = kln['s'].upper()
            new_kln = { '_t': int(kln['t']), '_o': float(kln['o']), '_h': float(kln['h']), '_l': float(kln['l']), '_c': float(kln['c']), '_v': float(kln['q']) }
            SymKlns[symbol].append(new_kln)
            print( '%d. %s\t' % (len(SymKlns[symbol]), symbol) + timestr(new_kln['_t']) + '\t' + \
                    ''.join(['{:>3}:{:<10}'.format(k, v) for k,v in iter(new_kln.items()) if not k=='_t']))
    elif mess['e'] == 'depthUpdate':


        ### PROBLEM 1 Insert your code to handle depthUpdate message ###


        pass

def on_error(ws, error):
    '''
    Do something when websocket has an error
    '''
    pass

def on_close(ws):
    '''
    Do something when websocket closes
    '''
    pass

def on_open(ws, *args):
    '''
    Main function to run multi-threading
    '''
    def data_stream(*args):
        params = [str.lower(ins) + str(s) for ins in insIds for s in stream]
        print(params)
        ws.send(json.dumps({"method": "SUBSCRIBE", "params": params, "id": 1 }))
        sub_time = time.time()
        while time.time() - start_time < run_time: #
            if time.time() - sub_time > 20*60:
                client.keepalive_stream() 
                sub_time = time.time()
        ws.close()
     
    t1 = threading.Thread(target=data_stream)        
    t1.start()

def header_print(testnet, client):
    '''
    Print general information of the trading session
    '''
    t_server, t_local = client.timestamp(), time.time()*1000
    print('\tTestnet: %s' % str(testnet))
    print('\tServer Time at Start: %s' % timestr(t_server))
    print('\tLocal Time at Start: %s, \tOffset (local-server): %d ms\n' % (timestr(t_local), (t_local-t_server)))
    try:
        bal_st = pd.DataFrame(client.balance())
        bal_st['updateTime'] = [timestr(b) for b in bal_st['updateTime']]
        print('\nBeginning Balance Info: \n')
        print(bal_st)
    except Exception:
         print('\nFail to connect to client.balance: \n')

start_time = time.time()
run_time = 3*60 #second
testnet = True
if testnet:
    # Testnet
    apikey = '' ### INSERT your api key here ###
    scrkey = '' ### INSERT your api secret here ###
else:
    # Binance
    apikey = ''
    scrkey = ''
insIds = [  'BTCUSDT', 'ETHUSDT', 'BCHUSDT' ]
stream = [] ### PROBLEM 1 INSERT your stream subscription here ###
BidAsk = {}
AggTrades = {}
SymKlns = {}
client = Client(apikey, scrkey, testnet=testnet)
client.change_position_mode(dualSide='true')
for symbol in insIds:
   client.change_leverage(symbol, 1)
   BidAsk[symbol] = []
   AggTrades[symbol] = []
   SymKlns[symbol] = []

print('\n' + barstr(text='Start Data Streaming') + '\n')     
header_print(testnet, client)
print('\nStream updating...')
listen_key = client.get_listen_key()
ws = websocket.WebSocketApp(f'{client.wss_way}{listen_key}',
                            on_message=on_message, 
                            on_error=on_error,
                            on_close=on_close)
ws.on_open = on_open
ws.run_forever()
client.close_stream()

print('\n\tLocal Time at Close: %s \n' % timestr(time.time()*1000))
print(barstr(text='Elapsed time = {} seconds'.format(round(time.time()-start_time,2))))
print(barstr(text="", space_size=0))
os._exit(1)