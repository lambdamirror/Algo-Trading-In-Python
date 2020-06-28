# -*- coding: utf-8 -*-
"""
Created on Sat May 24 00:16:07 2020

@author: tranl
"""
import numpy as np
import pandas as pd

def OBVol(df):
    '''
    Returns on-balance volume
    '''
    _obv = np.zeros(df.shape[0])
    _obv[0] = df['_v'].iloc[0]
    for i in range(1, df.shape[0]):
        if df['_c'].iloc[i] > df['_c'].iloc[i-1]:
            _obv[i] = _obv[i-1] + df['_v'].iloc[i]
        elif df['_c'].iloc[i] == df['_c'].iloc[i-1]:
            _obv[i] = _obv[i-1] 
        elif df['_c'].iloc[i] < df['_c'].iloc[i-1]:     
            _obv[i] = _obv[i-1] - df['_v'].iloc[i]
    return _obv

def MACD(df, fpd=12, spd=26):
    '''
    Returns moving average convergence/divergence
    '''
    fastema = df['_c'].ewm(span=fpd).mean()
    slowema = df['_c'].ewm(span=spd).mean()
    _macd = fastema - slowema
    return _macd

def Williams(df, period=14):
    """ returns Williams indicator """
    low = df['_l'].rolling(period).min()
    high = df['_h'].rolling(period).max()
    _will = -100*(high-df['_c'])/(high-low)
    return _will

def StochOsc(df, period=14):
    '''
    Returns stochastic oscilatior indicator
    '''
    low = df['_l'].rolling(period).min()
    high = df['_h'].rolling(period).max()
    _stoch = 100*(df['_c']-low)/(high-low)
    return _stoch

def RSIfunc(df, period=14):
    '''
    Returns RSI values
    '''
    diff = df['_c'].diff().dropna()
    first = diff.iloc[:period]
    _rsi = np.zeros(df['_c'].shape[0])
    _rsi[:period] = np.nan
    gain = np.zeros(df['_c'].shape[0] - period)
    loss = np.zeros(df['_c'].shape[0] - period)
    gain[0] = abs(first[first>0].sum())
    loss[0] = abs(first[first<0].sum())    
    for i in range(1, len(gain)):
        change = diff.iloc[period+i-1]
        gain[i] = gain[i-1]*(period-1)/period + abs(change*int(change>0))
        loss[i] = loss[i-1]*(period-1)/period + abs(change*int(change<0))
    for i in range(gain.shape[0]):
        if loss[i] == 0:
            _rsi[i+period] = 100
        else:
            _rsi[i+period] = 100 - 100/(1+gain[i]/loss[i])
    return _rsi

def Bbands(df, window=None, width=None, numsd=None):
    '''
    Returns average, upper band, and lower band
    '''
    ave = df.rolling(window).mean()
    sd = df.rolling(window).std(ddof=0)
    if width:
        upband = ave * (1+width)
        dnband = ave * (1-width)
        return ave, upband, dnband        
    if numsd:
        upband = ave + (sd*numsd)
        dnband = ave - (sd*numsd)
        return ave, upband, dnband   

def average_true_range(df, period=10, alpha=0.5, highlow=True):   
    '''
    Returns average true range at quantile alpha and percentage on average mid point
    '''
    _tr = df.copy()
    _tr['h-l'] = _tr['_h'].rolling(period).max() - _tr['_l'].rolling(period).min()
    _tr['h-o'] = (_tr['_h'].rolling(period).max() - _tr['_c'].shift(period)).abs()
    _tr['l-o'] = (_tr['_l'].rolling(period).min() - _tr['_c'].shift(period)).abs()
    if highlow:
        atr = pd.concat([_tr['h-l'], _tr['h-o'], _tr['l-o']], axis=1).dropna().max(axis=1).quantile(alpha)
    else:
        atr = pd.concat([_tr['h-o'], _tr['l-o']], axis=1).dropna().max(axis=1).quantile(alpha)
    atr_pct = atr/((_tr['_h'] + _tr['_l'])/2).mean()
    return atr, atr_pct