# -*- coding: utf-8 -*-
"""
Created on Sat May 7 00:16:07 2020

@author: tranl
"""
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
from ultilities import barstr, timestr

###TRADING RULES
QUANTPRE = {  'BTCUSDT': 3, 'ETHUSDT': 3, 'BCHUSDT': 3, 'XRPUSDT': 1, 'EOSUSDT': 1, 'LTCUSDT': 3, \
                'TRXUSDT': 0, 'ETCUSDT': 2, 'LINKUSDT': 2, 'XLMUSDT': 0, 'ADAUSDT': 0, 'XMRUSDT': 3, \
                'DASHUSDT': 3, 'ZECUSDT': 3, 'XTZUSDT': 1, 'BNBUSDT': 2, 'ATOMUSDT': 2, 'ONTUSDT': 1, \
                'IOTAUSDT': 1, 'BATUSDT': 1, 'VETUSDT': 0, 'NEOUSDT': 2, 'QTUMUSDT': 1, 'IOSTUSDT': 0 }
PRICEPRE = {  'BTCUSDT': 2, 'ETHUSDT': 2, 'BCHUSDT': 2, 'XRPUSDT': 2, 'EOSUSDT': 3, 'LTCUSDT': 2, \
              'TRXUSDT': 5, 'ETCUSDT':3, 'LINKUSDT': 3  , 'XLMUSDT': 5, 'ADAUSDT': 5, 'XMRUSDT': 2, \
              'DASHUSDT': 2, 'ZECUSDT': 2, 'XTZUSDT': 3, 'BNBUSDT': 3, 'ATOMUSDT': 3, 'ONTUSDT': 4, \
              'IOTAUSDT': 4, 'BATUSDT': 4, 'VETUSDT': 6, 'NEOUSDT': 3, 'QTUMUSDT': 3, 'IOSTUSDT': 6 }

SIDE = {'BUY': 1.0, 'SELL': -1.0}
             
min_in_ms = int(60*1000)
sec_in_ms = 1000

###%%%
    
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
                 timeInForce: float = None, 
                 cbRate: float = None):
        '''
        
        Signal class to monitor price movements
        
        To change currency pair     -> symbol = 'ethusdt'
        
        To change side              -> side = 'BUY'/'SELL'
        
        To change order size        -> size = float (dollar amount)
        
        To change order type        -> orderType = 'MARKET'/'LIMIT'/'TRAILING_STOP_MARKET'
        
        To change price             -> price = float (required for 'LIMIT' order type)
        
        stopLoss, takeProfit -- dollar amount
        
        To change time in force     -> timeInForce =  'GTC'/'IOC'/'FOK' (reuired for 'LIMIT' order type)
        
        To change call back rate    -> cbRate = float (required for 'TRAILING_STOP_MARKET' order type)
        
        '''
        self.symbol = symbol
        self.side = side #BUY, SELL
        self.positionSide = positionSide #LONG, SHORT
        self.orderType = orderType #LIMIT, MARKET, STOP, TAKE_PROFIT, TRAILING_STOP_MARKET
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
            return None
        else:
            exit_sign = None
            if lastTime is None or lastPrice is None:
                _t, _p = self.pricePath[-1]['timestamp'], self.pricePath[-1]['price']
            else:
                _t, _p = int(lastTime), float(lastPrice)
                
            ### PROBLEM 1, 4 : Insert your code here ###
            
            
            self.exitSign = exit_sign
            return exit_sign

    def __str__(self):
        '''
        Print out infomation of the signal
        
        '''
        s = 'Singal info: ' + self.symbol
        gen_ =  ' status:' + str(self.status) + ' side:' + str(self.side) + ' type:' + str(self.orderType) + ' quantity:' + str(self.get_quantity())
        if self.is_waiting() or self.is_expired():
            id_ = ' Id:None '
            price_ = ' price:' + str(self.price) + ' time:' + timestr(self.startTime, end='s')
            s += id_ + gen_ + price_


        ### PROBLEM 2 : Insert your code here ###


        return s
        
#%%%%

class Backtester:
    def __init__(self,
                 symbol: str,
                 tradeData,
                 initBalance: float = 1000,
                 orderSize: float = 100,
                 signalList: list = [],
                 commRate = {'MARKET': 0.032/100, 'LIMIT': 0.016/100}):
        self.symbol = symbol
        self.tradeData = tradeData
        self.balancePath = pd.DataFrame([{'_t': self.tradeData['_t'].iloc[0], '_b': initBalance}])
        self.orderSize = orderSize
        self.signalList = signalList
        self.commRate = commRate
    '''
        
    Backtester class to monitor trading session
    
    symbol : str -> symbol = 'BTCUSDT' 
    
    tradeData : pd.DataFrame(columns=['_t', '_p']
    
    '''
    def set_trade_data(self, tradeData):
        '''
        Resets tradeData
        '''
        self.tradeData = tradeData
        
    def add_signal(self, signal):
        '''
        Adds a closed signal to the signalList
        '''
        self.signalList.append(signal)
        return self.signalList
    
    def balance_update(self):
        '''
        Compeltes the balance path for every point in tradeData
        '''
        if len(self.signalList)==0:
            return self.balancePath
        t_start = self.balancePath['_t'].iloc[-1]
        _trades = self.tradeData[self.tradeData['_t']>=t_start] 
        for i in tqdm(range(1, _trades.shape[0]), disable=True):
            last_trade = _trades.iloc[i-1]
            new_trade =  _trades.iloc[i]
            tradeTime, change = new_trade['_t'], 0
            for sig in self.signalList:
                if last_trade['_t'] < sig.excTime and sig.excTime <= tradeTime:
                    change -= self.commRate[sig.orderType]*sig.get_quantity()*sig.excPrice
                    change += SIDE[sig.side]*sig.get_quantity()*(new_trade['_p'] - sig.excPrice)
                if last_trade['_t'] < sig.clsTime and sig.clsTime <= tradeTime:
                    change -= self.commRate[sig.cntType]*sig.get_quantity()*sig.clsPrice
                    change += SIDE[sig.side]*sig.get_quantity()*(sig.clsPrice - last_trade['_p'])
                if sig.excTime < last_trade['_t'] and tradeTime < sig.clsTime:
                    change += SIDE[sig.side]*sig.get_quantity()*(new_trade['_p'] - last_trade['_p'])
            last_update = self.balancePath.iloc[-1]
            self.balancePath = self.balancePath.append({'_t': int(tradeTime), '_b': float(last_update['_b']+change)}, ignore_index=True)
        return self.balancePath
     
    def gross_profit(self):
        '''
        Returns gross profit
        '''
        win_trade = 0
        profit = 0
        for sig in self.signalList:
            pos = SIDE[sig.side]*sig.get_quantity()*(sig.clsPrice - sig.excPrice)
            if pos > 0:
                win_trade += 1
                profit += abs(pos)
        return win_trade, profit
    
    def gross_loss(self):
        '''
        Returns gross loss
        '''
        loss_trade = 0
        loss = 0
        for sig in self.signalList:
            pos = SIDE[sig.side]*sig.get_quantity()*(sig.clsPrice - sig.excPrice)
            if pos < 0:
                loss_trade += 1
                loss += abs(pos)
        return loss_trade, loss
    
    def commision(self):
        '''
        Returns commission fees
        '''
        comm = 0
        for sig in self.signalList:
            comm += sig.get_quantity()*(self.commRate[sig.orderType]*sig.excPrice + \
                                        self.commRate[sig.cntType]*sig.clsPrice)
        return comm    
        
    def net_profit(self, commision=True):
        '''
        Returns net profit (gross after commission)
        '''
        net = self.gross_profit()[1] - self.gross_loss()[1]
        if commision:
            net -= self.commision()
        return net
    
    def total_trades(self):
        '''
        Returns number of total trades
        '''
        return len(self.signalList)
    
    def time_in_position(self):
        '''
        Returns time in positions
        '''
        total_time = 0
        for sig in self.signalList:
            total_time += (sig.clsTime - sig.excTime)/1000
        return total_time
    
    def profit_factor(self, maxRatio=1000):
        '''
        Returns profit factor
        '''
        win_trade, profit = self.gross_profit()
        loss_trade, loss = self.gross_loss()
        if win_trade > 0 and loss_trade > 0:
            return round(win_trade/loss_trade, 4), round(profit/loss, 4)
        elif win_trade==0:
            return 0, 0
        else:
            return maxRatio, maxRatio

    def summary(self):
        '''
        Print out the summary statistics
        '''
        trading_time = (self.tradeData['_t'].iloc[-1] - self.tradeData['_t'].iloc[0])/(1000*60*60)
        loss, gross_loss = self.gross_loss()
        win, gross_profit = self.gross_profit()
        comm = self.commision()
        net_profit = self.net_profit()
        total_trades = self.total_trades()
        break_even = total_trades - (win+loss)
        if total_trades > 0:
            time_av = self.time_in_position()/total_trades/60
        else:
            time_av = 0
 
        print( '\n' + barstr(text='Backtester Summary', symbol='#', length=80, space_size=5) + '\n' )
        print( '\n\tSymbol: %s' % (self.symbol))  
        print( '\tTrading Time: \t%1.2f h' % trading_time)      
        print( '\n\tGross Profit: \t%1.5f' % gross_profit)
        print( '\tGross Loss: \t%1.5f' % gross_loss)
        print( '\tCommision: \t%1.5f' % comm)
        print( '\tNet Profit: \t%1.5f' % (net_profit))
        print( '\tTotal number of trades: \t%d' % (total_trades))
        print( '\tNumber of win trades: \t%d' % (win))
        print( '\tNumber of loss trades: \t%d' % (loss))
        print( '\tAverage time in position: \t%1.2f mins' % (time_av))   

###%%%
