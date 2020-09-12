# -*- coding: utf-8 -*-
"""
Created on Sat Mar 24 00:16:07 2020

@author: tranl
"""
import time, sys, math
import numpy as np
import pandas as pd

from tqdm import tqdm
from binancepy import MarketData
from indicators import Bbands, average_true_range
from utility import timestr, print_
###TRADING RULES
QUANTPRE = {  'BTCUSDT': 3, 'ETHUSDT': 3, 'BCHUSDT': 2, 'XRPUSDT': 1, 'EOSUSDT': 1, 'LTCUSDT': 3, \
                'TRXUSDT': 0, 'ETCUSDT': 2, 'LINKUSDT': 2, 'XLMUSDT': 0, 'ADAUSDT': 0, 'XMRUSDT': 3, \
                'DASHUSDT': 3, 'ZECUSDT': 3, 'XTZUSDT': 1, 'BNBUSDT': 2, 'ATOMUSDT': 2, 'ONTUSDT': 1, \
                'IOTAUSDT': 1, 'BATUSDT': 1, 'VETUSDT': 0, 'NEOUSDT': 2, 'QTUMUSDT': 1, 'IOSTUSDT': 0 }
PRICEPRE = {  'BTCUSDT': 2, 'ETHUSDT': 2, 'BCHUSDT': 2, 'XRPUSDT': 4, 'EOSUSDT': 3, 'LTCUSDT': 2, \
              'TRXUSDT': 5, 'ETCUSDT':3, 'LINKUSDT': 3  , 'XLMUSDT': 5, 'ADAUSDT': 5, 'XMRUSDT': 2, \
              'DASHUSDT': 2, 'ZECUSDT': 2, 'XTZUSDT': 3, 'BNBUSDT': 3, 'ATOMUSDT': 3, 'ONTUSDT': 4, \
              'IOTAUSDT': 4, 'BATUSDT': 4, 'VETUSDT': 6, 'NEOUSDT': 3, 'QTUMUSDT': 3, 'IOSTUSDT': 6 }

SIDE = {'BUY': 1.0, 'SELL': -1.0}

min_in_ms = int(60*1000)
sec_in_ms = 1000

###%%%

class Portfolio:
    def __init__( self,
                  client,
                  tradeIns = []):
        '''
        Portfolio class
        '''
        self.client = client
        self.tradeIns = tradeIns.copy()
        self.orderSize = 0
        self.equityDist = {'BUY': 0, 'SELL': 0}
        self.locks = { 'BUY': [], 'SELL': []}
        
    def equity_distribution(self, longPct=0.5, shortPct=0.5, currency='USDT', orderPct=0.1):
        '''
        Retrun number of buy/sell orders with currenty equity
        
            longPct : percentage of equity assigned for buying
        
            shortPct : percentage of equity assigned for selling
        
            orderPct : percentage of equity for a single order
        '''
        balance = self.client.balance()
        equity, available = 0, 0
        for b in balance:
            if b['asset']==currency:
                equity, available = float(b['balance']), float(b['withdrawAvailable'])
                break
        long_equity = longPct*equity
        short_equity = shortPct*equity
        
        info = pd.DataFrame(self.client.position_info())
        short_info = info[info['positionAmt'].astype(float) < 0]
        long_info = info[info['positionAmt'].astype(float) > 0]
        short_position = abs(short_info['positionAmt'].astype(float) @ short_info['entryPrice'].astype(float))
        long_position = abs(long_info['positionAmt'].astype(float) @ long_info['entryPrice'].astype(float))
        
        self.orderSize = round(orderPct*equity, 2)
        long_order = int((long_equity - long_position)/self.orderSize)
        short_order = int((short_equity - short_position)/self.orderSize)
        self.equityDist = {'BUY': long_order, 'SELL': short_order}
        return long_order, short_order
        
    def position_locks(self, prelocks={ 'BUY': [], 'SELL': []}):
        '''
        Check for open positions and return a tradable instruments
        '''
        info = self.client.position_info()
        self.locks = prelocks
        for pos in info:
            amt = float(pos['positionAmt'])
            if amt < 0 and not pos['symbol'] in self.locks['SELL']: self.locks['SELL'].append(pos['symbol'])
            elif amt > 0 and not pos['symbol'] in self.locks['BUY']: self.locks['BUY'].append(pos['symbol'])
        drop_out = set(self.locks['SELL']).intersection(self.locks['BUY'])
        for s in drop_out: self.tradeIns.remove(s)
        return self.tradeIns

###%%%

class TradingModel:
    def __init__( self,
                  symbol: str,
                  testnet: bool,
                  modelType: str,
                  marketData,
                  pdObserve: int,
                  pdEstimate: int,
                  features: dict = None,
                  inputData = None,
                  orderSize = 1.0, #USDT
                  breath: float = 0.01/100):
        '''
        Trading Model class
        '''
        self.symbol = symbol
        self.testnet = testnet
        self.modelType = modelType
        self.marketData = marketData
        self.pdObserve = pdObserve
        self.pdEstimate = pdEstimate
        self.inputData = inputData
        self.timeLimit = int(self.pdObserve*10)
        self.orderSize = orderSize
        self.breath = breath
        self.signalLock = []

    def add_signal_lock(self, slock=None):
        '''
        Add a signal to lock positions i.e. abandon BUY/SELL the instrument
        '''
        if (slock is not None) and (not slock in self.signalLock):
            self.signalLock.append(slock)

    def remove_signal_lock(self, slock=None):
        '''
        Remove a signal from lock positions i.e. allows BUY/SELL the instrument
        '''    
        if (slock is not None) and (slock in self.signalLock):
            self.signalLock.remove(slock)

    def build_initial_input(self, period=180):
        '''
        Download and store historical data
        '''
        if self.modelType=='bollinger':
            min_in_candle = 1
            num_klns = period
            t_server = self.marketData.server_time()['serverTime']
            t_start = t_server - num_klns*min_in_candle*60*1000
            df = klns_to_df(self.marketData.candles_data(interval='1m', startTime=t_start, limit=num_klns), ['_t', '_o', '_h', '_l', '_c', '_v'])
            if self.inputData is None:
                self.inputData = df
            else:
                df = df[df['_t'] > self.inputData['_t'].iloc[-1]]
                self.inputData = self.inputData.append(df, ignore_index=True)
        return self.inputData

    def get_last_signal(self, dataObserve=None):
        '''
        Process the lastest data for a potential singal
        '''
        if self.modelType=='bollinger':
            _data = dataObserve[dataObserve['_t'] > self.inputData['_t'].iloc[-1]]
            _data = self.inputData.append(_data, ignore_index=True)
            
            _, bb_up, bb_down = Bbands(_data['_c'], window=self.pdEstimate, numsd=2.5)
            # up cross
            crit1 = _data['_c'].shift(1) < bb_up.shift(1)
            crit2 = _data['_c'] > bb_up
            up_cross = _data[crit1 & crit2]
            # down cross
            crit1 = _data['_c'].shift(1) > bb_down.shift(1)
            crit2 = _data['_c'] < bb_down
            dn_cross = _data[crit1 & crit2]

            _data['side'] = np.zeros(_data.shape[0])
            _data.loc[up_cross.index, 'side'] = -1.
            _data.loc[dn_cross.index, 'side'] = 1.
            _side = _data['side'].iloc[-1]

            atr, _ = average_true_range(_data.copy(), period=self.pdEstimate, alpha=0.3, highlow=False)
  
            if _side == 1. and not 'BUY' in self.signalLock:
                return {'side': 'BUY', 'positionSide': 'LONG', '_t': _data['_t'].iloc[-1], '_p': _data['_c'].iloc[-1], 'atr' : atr}
            elif _side == -1. and not 'SELL' in self.signalLock:
                return {'side': 'SELL', 'positionSide': 'SHORT', '_t': _data['_t'].iloc[-1], '_p': _data['_c'].iloc[-1], 'atr' : atr}
        return None

#%%%%

class Signal:
    def __init__(self,
                 symbol: str,
                 side: str,
                 size: float,
                 orderType: str, 
                 positionSide: str = 'BOTH',
                 price: float = None,
                 startTime: int = time.time()*1000,
                 expTime: float = (time.time()+60)*1000,
                 stopLoss: float = None, 
                 takeProfit: float = None, 
                 timeLimit: int = None, #minutes
                 timeInForce: float = None):
        '''
        
        Signal class to monitor price movements
        
        To change currency pair     -> symbol = 'ethusdt'
        
        To change side              -> side = 'BUY'/'SELL'
        
        To change order size        -> size = float (dollar amount)
        
        To change order type        -> orderType = 'MARKET'/'LIMIT'
        
        To change price             -> price = float (required for 'LIMIT' order type)
        
        stopLoss, takeProfit -- dollar amount
        
        To change time in force     -> timeInForce =  'GTC'/'IOC'/'FOK' (reuired for 'LIMIT' order type)
        
        '''
        self.symbol = symbol
        self.side = side #BUY, SELL
        self.positionSide = positionSide #LONG, SHORT
        self.orderType = orderType #LIMIT, MARKET, STOP, TAKE_PROFIT
        # predefined vars
        self.price = float(price)
        if size < self.price*10**(-QUANTPRE[symbol]):
            size = self.price*10**(-QUANTPRE[symbol])*1.01
        self.size = float(size) #USDT
        self.quantity = round(self.size/self.price, QUANTPRE[self.symbol])
        self.startTime = int(startTime)
        self.expTime = expTime
        # 3 exit barriers
        if stopLoss is not None: self.stopLoss = round(float(stopLoss), 4)
        else: self.stopLoss = None
        if takeProfit is not None: self.takeProfit = round(float(takeProfit), 4)
        else: self.takeProfit = None
        if timeLimit is not None: self.timeLimit = int(timeLimit*sec_in_ms) # miliseconds
        else: self.timeLimit = None

        self.timeInForce = timeInForce
        self.status = 'WAITING' #'ORDERED' #'ACTIVE' #'CNT_ORDERED' #'CLOSED' # 'EXPIRED'
        self.limitPrice, self.orderTime = None, None
        self.excPrice, self.excTime = None, None
        self.cntlimitPrice, self.cntTime, self.cntType = None, None, None
        self.clsPrice, self.clsTime = None, None
        self.orderId = None
        self.cntorderId = None
        self.pricePath = []
        self.exitSign = None
    
    '''
    Function to check and set STATUS of the signals : 
        - WAITING
        - ORDERED
        - ACTIVE
        - CNT_ORDERED
        - CLOSED
        - EXPIRED
    '''
    def is_waiting(self):
        return bool(self.status == 'WAITING')
        
    def set_waiting(self):
        self.status = 'WAITING'
        
    def is_ordered(self):
        return bool(self.status == 'ORDERED')
        
    def set_ordered(self, orderId, orderTime=None, limitPrice=None):
        self.status = 'ORDERED'        
        self.orderId = int(orderId)
        self.orderTime, self.limitPrice = orderTime, limitPrice
    
    def is_active(self):
        return bool(self.status == 'ACTIVE')
        
    def set_active(self, excTime=time.time()*1000, excPrice=None, excQty: float = None):
        self.excPrice = float(excPrice)
        self.excTime = int(excTime)
        self.quantity = round(float(excQty), QUANTPRE[self.symbol])
        self.status = 'ACTIVE'   
    
    def is_cnt_ordered(self):
        return bool(self.status == 'CNT_ORDERED')
        
    def set_cnt_ordered(self, cntorderId, cntType=None, cntTime=None,  cntlimitPrice=None):
        self.status = 'CNT_ORDERED'
        self.cntorderId = int(cntorderId)
        self.cntType, self.cntTime, self.cntlimitPrice = cntType, cntTime, cntlimitPrice

    def is_closed(self):
        return bool(self.status == 'CLOSED')

    def set_closed(self, clsTime=time.time()*1000, clsPrice=None):
        self.clsTime = int(clsTime)
        if clsPrice is not None: self.clsPrice = float(clsPrice)
        else: self.clsPrice = None        
        self.status = 'CLOSED' 

    def is_expired(self):
        return bool(self.status == 'EXPIRED')

    def set_expired(self):
        self.status = 'EXPIRED'   

    def get_quantity(self):
        '''
        Return quantity
        '''
        return self.quantity
        
    def counter_order(self):
        ''' 
        Return counter (close) order with same size but opposite side
        '''
        if self.side=='BUY': side = 'SELL'
        else: side = 'BUY'
        if self.positionSide == 'LONG': posSide = 'SHORT'
        elif self.positionSide =='SHORT': posSide = 'LONG'
        else: posSide = 'BOTH'
        counter = {'side': side, 'positionSide': posSide, 'type': self.orderType, \
                    'amt': self.get_quantity(),'TIF': self.timeInForce}
        return counter

    def path_update(self, lastPrice, lastTime):
        '''
        Update last traded prices to pricePath 
        '''
        self.pricePath.append({'timestamp': int(lastTime), 'price': float(lastPrice)})

    def get_price_path(self):
        '''
        Return price movements since the entry
        '''
        return pd.DataFrame(self.pricePath)

    def exit_triggers(self, lastTime=None, lastPrice=None, retrace=False):
        ''' 
        Return a exit signal upon 3 barrier triggers
        '''
        if not self.is_active() or len(self.pricePath)<=1:
            return None, None
        else:
            exit_sign = None
            if lastTime is None and lastPrice is None:
                _t, _p = self.pricePath[-1]['timestamp'], self.pricePath[-1]['price']
            pos = SIDE[self.side]*(_p - self.excPrice)
            if self.takeProfit is not None and pos > self.takeProfit: 
                exit_sign = 'takeProfit'
            if self.stopLoss is not None:
                if retrace: 
                    prices = pd.DataFrame(self.pricePath)
                    prices['pos'] = SIDE[self.side]*(prices['price'] - self.excPrice)
                    loss_idx = prices.idxmin(axis=0)['pos']
                    max_loss = prices.loc[loss_idx]['pos']
                    foundSL = (max_loss < -1.0*self.stopLoss) and (pos > -0.5*self.stopLoss)
                else: foundSL = (pos < -1.0*self.stopLoss)
                if foundSL: exit_sign = 'stopLoss'
            if self.timeLimit is not None and _t - self.excTime >= self.timeLimit and pos > 0: 
                exit_sign = 'timeLimit'
            self.exitSign = exit_sign
            return exit_sign, pos

    def __str__(self):
        '''
        Print out infomation of the signal
        '''
        s = 'Singal info: ' + self.symbol
        gen_ =  ' status:' + str(self.status) + ' side:' + str(self.side) + ' type:' + str(self.orderType) + ' quantity:' + str(self.get_quantity())
        if self.is_waiting() or self.is_expired():
            id_ = ' Id:None '
            price_ = ' price:' + str(self.price) + ' time:' + timestr(self.startTime, end='s')
        elif self.is_ordered():
            id_ = ' Id:'+ str(self.orderId)
            if self.orderType=='LIMIT':
                price_ = ' price:' + str(self.limitPrice) + ' TIF:' + str(self.timeInForce) + ' time:' + timestr(self.startTime, end='s')
            else: price_ = ' type:' + str(self.orderType) + ' time:' + timestr(self.orderTime, end='s')
        elif self.is_active():
            id_ = ' Id:'+ str(self.orderId)
            if self.orderType=='LIMIT':
                price_ = ' price:' + str(self.excPrice) + ' TIF:' + str(self.timeInForce) + ' time:' + timestr(self.excTime, end='s')
            else: price_ = ' price:' + str(self.excPrice) + ' time:' + timestr(self.excTime, end='s')
        elif self.is_cnt_ordered():
            gen_ = ' status:' + str(self.status) + ' side:' + str(self.counter_order()['side']) + ' type:' + str(self.cntType) + ' quantity:' + str(self.get_quantity())
            id_ = ' Id:'+ str(self.cntorderId)
            if self.cntType=='LIMIT':
                price_ = ' price:' + str(self.cntlimitPrice) + ' TIF:' + str(self.timeInForce) + ' time:' + timestr(self.cntTime, end='s')
            else: price_ = ' type:' + str(self.cntType) + ' time:' + timestr(self.cntTime, end='s')
        elif self.is_closed():
            gen_ = ' status:' + str(self.status) + ' side:' + str(self.counter_order()['side']) + ' type:' + str(self.cntType) + ' quantity:' + str(self.get_quantity())
            id_ = ' Id: ' + str(self.cntorderId)
            price_ = ' price:' + str(self.clsPrice) + ' time:' + timestr(self.clsTime, end='s')
        if self.stopLoss is None: sl_ = 'None'
        else: sl_ = str(self.stopLoss)
        if self.takeProfit is None: tp_ = 'None'
        else: tp_ = str(self.takeProfit)
        if self.timeLimit is None: tl_ = 'None'
        else: tl_ = str(int(self.timeLimit/sec_in_ms))
        exits_ = ' exits:[' + sl_ + ', ' + tp_ + ', ' + tl_ + ']'
        s += id_ + gen_ + price_ + exits_
        return s

###%%%

def klns_to_df(market_data, feats):
    '''
    Return a pd.DataFrame from candles data received from the exchange
    '''
    fts = list(str(f) for f in feats)
    df_ = pd.DataFrame(market_data, columns = ['_t', '_o', '_h', '_l', '_c', '_v', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
    df_[['_o', '_h', '_l', '_c', '_v']] = df_[['_o', '_h', '_l', '_c', '_v']].astype(float)
    return df_[fts]
