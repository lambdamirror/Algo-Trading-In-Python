# -*- coding: utf-8 -*-
"""
Created on Sat Mar 24 00:16:07 2020

@author: tranl

CREDIT: This is a modified version from the original module of morozdima.
        For more information, please visit: https://github.com/morozdima/BinanceFuturesPy
        
Docmentation of Binance Futures Websocket can be found here: https://binance-docs.github.io/apidocs/futures/en
"""

import time

import numpy as np
import pandas as pd

import requests
import urllib
import json
import hmac
import hashlib

#%%%%     
class MarketData:
    def __init__(self,
                 testnet: bool = False,
                 symbol: str = 'btcusdt'):

        '''
        
        To use TESTNET Binance Futures API  -> testnet = True
        
        To change currency pair             -> symbol = 'ethusdt'
        
        '''

        if testnet == True:
            self.http_way = 'http://testnet.binancefuture.com/fapi/v1/'
        else:
            self.http_way = 'http://fapi.binance.com/fapi/v1/'

        self.symbol = symbol.lower()

    def ping(self):
        return requests.get(f'{self.http_way}ping').json()

    def server_time(self):
        return requests.get(f'{self.http_way}time').json()

    def exchange_info(self):
        return requests.get(f'{self.http_way}exchangeInfo').json()

    def order_book(self, limit: int = 100):
        '''
        To change limit -> limit = 1000
        (Valid limits:[5, 10, 20, 50, 100, 500, 1000])
        '''
        r = requests.get(f'{self.http_way}depth?symbol={self.symbol}&limit={limit}')
        try:
            return r.json()
        except:
            if str(r) == '<Response [200]>':
                return dict([])
            else:
                return r
    
    def recent_trades(self, limit: int = 500):
        '''
        To change limit -> limit = 1000
        (max 1000)
        '''
        r = requests.get(f'{self.http_way}trades?symbol={self.symbol}&limit={limit}')
        try:
            return r.json()
        except:
            if str(r) == '<Response [200]>':
                return dict([])
            else:
                return r
    
    def historical_trades(self, limit: int = 500):
        '''
        To change limit -> limit = 1000
        (max 1000)
        '''
        return requests.get(f'{self.http_way}historicalTrades?symbol={self.symbol}&limit={limit}').json()
    
    def aggregate_trades(self,
                         fromId: int = None,
                         startTime: int = None,
                         endTime: int = None,
                         limit: int = 500):
        '''
        To change limit                     ->  limit = 1000
        (max 1000)
        
        To use fromId                       ->  fromId = 1231
        To use start time and end time      ->  startTime = 1573661424937
                                            ->  endTime = 1573661428706
        '''
        return requests.get(f'{self.http_way}aggTrades?symbol={self.symbol}&fromId={fromId}&startTime={startTime}&endTime={endTime}&limit={limit}').json()

    def candles_data(self,
                     interval: str = '1m',
                     startTime: int = None,
                     endTime: int = None,
                     limit: int = 500):
        '''
        To change interval                  ->  interval = '5m'
        (Valid values: [1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M])
        
        To use limit                        ->  limit = 1231
        (Default 500; max 1500)
        
        To use start time and end time      ->  startTime = 1573661424937
                                            ->  endTime = 1573661428706
        '''
        return requests.get(f'{self.http_way}klines?symbol={self.symbol}&interval={interval}&startTime={startTime}&endTime={endTime}&limit={limit}').json()
    
    def mark_price(self):
        return requests.get(f'{self.http_way}premiumIndex?symbol={self.symbol}').json()
    
    def funding_rate(self,
                     startTime: int = None,
                     endTime: int = None,
                     limit: int = 100):
        '''
        To change limit                     ->  limit = 1000
        (max 1096)
        
        To use start time and end time      ->  startTime = 1573661424937
                                            ->  endTime = 1573661428706
        '''
        return requests.get(f'{self.http_way}klines?symbol={self.symbol}&startTime={startTime}&endTime={endTime}&limit={limit}').json()
    
    def ticker_price_24h(self,
                         symbol: bool = False):
        if symbol is True:
            return requests.get(f'{self.http_way}ticker/24hr?symbol={self.symbol}').json()
        else:
            return requests.get(f'{self.http_way}ticker/24hr').json()
    
    def ticker_price_symbol(self,
                            symbol: bool = False):
        if symbol is True:
            return requests.get(f'{self.http_way}ticker/price?symbol={self.symbol}').json()
        else:
            return requests.get(f'{self.http_way}ticker/price').json()
    
    def ticker_orderbook_symbol(self,
                                symbol: bool = False):
        if symbol is True:
            return requests.get(f'{self.http_way}ticker/bookTicker?symbol={self.symbol}').json()
        else:
            return requests.get(f'{self.http_way}ticker/bookTicker').json()


#%%%%
class Client:
    def __init__(self,
                 api_key: str,
                 sec_key: str,
                 testnet: bool = False):
        '''
        In any case you must give your API key and API secret to work with Client
        
        To use TESTNET Binance Futures API  -> testnet = True
        '''
        
        self.api_key = api_key
        self.sec_key = sec_key
        self.X_MBX_APIKEY = {"X-MBX-APIKEY": self.api_key}
        
        if testnet == True:
            self.http_way = 'http://testnet.binancefuture.com/fapi/v1/'
            self.wss_way = 'wss://stream.binancefuture.com/ws/'
        else:
            self.http_way = 'http://fapi.binance.com/fapi/v1/'
            self.wss_way = 'wss://fstream.binance.com/ws/'
    
    
    '''
    Implied REST method: GET / POST / PUT / DELETE
    '''
    def _get_request(self,
                      req,
                      query):
        r = requests.get(self.request_url(req=req,
                                           query=query,
                                           signature=self.get_sign(query=query)),
                          headers=self.X_MBX_APIKEY)
        
        try:
            return r.json()
        except:
            if str(r) == '<Response [200]>':
                return dict([])
            else:
                return r
    
    def _post_request(self,
                      req,
                      query):
        r = requests.post(self.request_url(req=req,
                                           query=query,
                                           signature=self.get_sign(query=query)),
                          headers=self.X_MBX_APIKEY)
        
        try:
            return r.json()
        except:
            if str(r) == '<Response [200]>':
                return dict([])
            else:
                return r
    
    def _delete_request(self,
                      req,
                      query):
        r = requests.delete(self.request_url(req=req,
                                           query=query,
                                           signature=self.get_sign(query=query)),
                          headers=self.X_MBX_APIKEY)

        try:
            return r.json()
        except:
            if str(r) == '<Response [200]>':
                return dict([])
            else:
                return r
    
    def _put_request(self,
                      req,
                      query):
        r = requests.put(self.request_url(req=req,
                                           query=query,
                                           signature=self.get_sign(query=query)),
                          headers=self.X_MBX_APIKEY)
        try:
            return r.json()
        except:
            if str(r) == '<Response [200]>':
                return dict([])
            else:
                return r

    def timestamp(self):
        r = requests.get(f'{self.http_way}time')
        try:
            sv_time = r.json()
            return int(sv_time['serverTime'])
        except:
            if str(r) == '<Response [200]>':
                return dict([])
            else:
                return r

    def get_sign(self, query):
        
        return hmac.new(self.sec_key.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()

    def request_url(self, req, query, signature):
        
        return self.http_way + req + query + '&signature=' + signature

    def new_order(self,
                  symbol: str,
                  side: str,
                  orderType: str,
                  quantity: float,
                  positionSide: str = 'BOTH',
                  timeInForce: float = None,
                  reduceOnly: bool = False,
                  price: float = None,
                  newClientOrderId: str = None,
                  stopPrice: float = None,
                  activationPrice: float = None,
                  callbackRate: float = None,
                  workingType: str = None):
        '''
        POST
        
        Choose side:                SELL or BUY
        Choose quantity:            0.001
        Choose price:               7500
        Choose positionSide:        'LONG' or 'SHORT' or 'BOTH'

        To change order type    ->  orderType = 'MARKET'/'LIMIT'/'TRAILING_STOP_MARKET'
        To change time in force ->  timeInForce = 'GTC'/'IOC'/'FOK'
        '''
        
        req = 'order?'
        
        querystring = {'symbol' : symbol.lower(),
                       'side' : side,
                       'positionSide': positionSide,
                       'type' : orderType,
                       'quantity' : quantity}
        if positionSide == 'BOTH':
            querystring['reduceOnly'] = reduceOnly
        if timeInForce is not None:
            querystring['timeInForce'] = timeInForce
        if price is not None:
            querystring['price'] = price
        if newClientOrderId is not None:
            querystring['newClientOrderId'] = newClientOrderId
        if stopPrice is not None:
            querystring['stopPrice'] = stopPrice
        if workingType is not None:
            querystring['workingType'] = workingType
        if activationPrice is not None: 
            querystring['activationPrice'] = activationPrice
        if callbackRate is not None: 
            querystring['callbackRate'] = callbackRate
        querystring['timestamp'] = self.timestamp()
        
        querystring = urllib.parse.urlencode(querystring)

        return self._post_request(req, querystring)

    def query_order(self, symbol, orderId):
        '''
        GET
        
        Choose orderId: 156316486
        '''
        req = 'order?'
        querystring = urllib.parse.urlencode({'symbol' : symbol.lower(),
                                              'orderId' : orderId,
                                              'timestamp' : self.timestamp()})
    
        return self._get_request(req, querystring)

    def cancel_order(self, symbol, orderId):
        '''
        DELETE
        
        Choose orderId: 156316486
        '''
        req = 'order?'
        querystring = urllib.parse.urlencode({'symbol' : symbol.lower(),
                                              'orderId' : orderId,
                                              'timestamp' : self.timestamp()})

        return self._delete_request(req, querystring)

    def current_open_orders(self):
        '''
        GET
        '''
        req = 'openOrders?'
        querystring = urllib.parse.urlencode({'timestamp' : self.timestamp()})

        return self._get_request(req, querystring)

    def all_orders(self,
                   symbol: str,
                   limit: int = 1000,
                   startTime: int = None,
                   endTime: int = None):
        '''
        GET

        To change limit of output orders    ->  limit = 1000
        (max value is 1000)
        To use start time and end time      ->  startTime = 1573661424937
                                            ->  endTime = 1573661428706
        '''
        req = 'allOrders?'
        querystring = urllib.parse.urlencode({'symbol' : symbol.lower(),
                                              'timestamp' : self.timestamp(),
                                              'limit' : limit,
                                              'startTime' : startTime,
                                              'endTime' : endTime})

        return self._get_request(req, querystring)

    def balance(self):
        '''
        GET
        '''
        req = 'balance?'
        querystring = urllib.parse.urlencode({'timestamp' : self.timestamp()})

        return self._get_request(req, querystring)

    def account_info(self):
        '''
        GET
        '''
        req = 'account?'
        querystring = urllib.parse.urlencode({'timestamp' : self.timestamp()})

        return self._get_request(req, querystring)
    
    def change_position_mode(self, dualSide='false'):
        '''
        POST
        
        To change position mode: "true": Hedge Mode; "false": One-way Mode
        '''
        req = 'positionSide/dual?'
        querystring = urllib.parse.urlencode({'dualSidePosition' : dualSide,
                                              'timestamp' : self.timestamp()})

        return self._post_request(req, querystring)

    def change_leverage(self, symbol, leverage):
        '''
        POST
        
        To change leverage -> leverage = 25
        (from 1 to 125 are valid values)
        '''
        req = 'leverage?'
        querystring = urllib.parse.urlencode({'symbol' : symbol.lower(),
                                              'leverage' : leverage,
                                              'timestamp' : self.timestamp()})

        return self._post_request(req, querystring)

    def position_info(self):
        '''GET'''
        req = 'positionRisk?'
        querystring = urllib.parse.urlencode({'timestamp' : self.timestamp()})
        
        return self._get_request(req, querystring)

    def trade_list(self,
                   symbol: str,
                   limit: int = 1000,
                   startTime: int = None,
                   endTime: int = None):
        '''
        GET
        
        To change limit of output orders    -> limit = 1000
        (max value is 1000)
        To use start time and end time      -> startTime = 1573661424937
                                            -> endTime = 1573661428706
        '''
        req = 'userTrades?'
        querystring = urllib.parse.urlencode({'symbol' : symbol.lower(),
                                              'timestamp' : self.timestamp(),
                                              'limit' : limit,
                                              'startTime' : startTime,
                                              'endTime' : endTime})

        return self._get_request(req, querystring)

    def income_history(self,
                       symbol: str,
                       limit: int = 1000):
        '''
        GET
        
        To change limit of output orders    -> limit = 1000
        (max value is 1000)
        '''
        req = 'income?'
        querystring = urllib.parse.urlencode({'symbol' : symbol.lower(),
                                              'timestamp' : self.timestamp(),
                                              'limit' : limit})

        return self._get_request(req, querystring)

    def start_stream(self):
        '''
        POST
        '''
        req = 'listenKey?'
        querystring = urllib.parse.urlencode({'timestamp' : self.timestamp()})
        
        return self._post_request(req, querystring)

    def get_listen_key(self):
        return self.start_stream()['listenKey']

    def keepalive_stream(self):
        '''
        PUT
        '''
        req = 'listenKey?'
        querystring = urllib.parse.urlencode({'timestamp' : self.timestamp()})
        
        return self._put_request(req, querystring)

    def close_stream(self):
        '''
        DELETE
        '''
        req = 'listenKey?'
        querystring = urllib.parse.urlencode({'timestamp' : self.timestamp()})
        
        return self._delete_request(req, querystring)
        
#%%%%