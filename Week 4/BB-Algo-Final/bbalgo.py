# -*- coding: utf-8 -*-
"""
Created on Sat Mar 14 23:16:07 2020

@author: tranl
"""
import time, sys, os
import numpy as np
import pandas as pd

from binancepy import MarketData, Client
from utility import print_, barstr, timestr
from tradingpy import TradingModel, Portfolio
from wss import wss_run

## Model setups
min_in_candle = 1
pd_ob = int(30/min_in_candle)
pd_es = 15

def main(args):
    '''
    Main function : produce some predefined hyper-parameters before starting the trading session
    '''
    start_time = time.time()
    testnet = True
    filename = str(int(time.time()))
    if testnet:
        # Testnet
        apikey = '' ### INSERT your api key here ###
        scrkey = '' ### INSERT your api secret here ###
    else:
        # Binance
        apikey = ''
        scrkey = ''

    if testnet: fileout =  "report/testnet-" + filename
    else: fileout =  "report/" + filename

    insIds = [ 'BTCUSDT', 'ETHUSDT', 'BCHUSDT', 'BNBUSDT' ]
    
    # Generate Client object
    client = Client(apikey, scrkey, testnet=testnet)
    client.change_position_mode(dualSide='true')
    
    # Generate Portfolio object
    portfolio = Portfolio(client, tradeIns=insIds)
    long, short = portfolio.equity_distribution(longPct=0.25, shortPct=0.25, currency='USDT', orderPct=0.05)
    portfolio.position_locks()

    print_('\n' + barstr('', length=100, space_size=0), fileout)
    print_(barstr('BINANCE TRADING', length=100, space_size=5), fileout)
    print_(barstr('', length=100, space_size=0) + '\n', fileout)

    print_('\n' + barstr('Generating Models', length=100, space_size=5) + '\n', fileout)
    # Generate Models object
    models = {}
    for i in range(len(portfolio.tradeIns)):
        symbol = portfolio.tradeIns[i]
        client.change_leverage(symbol, 1)
        _data = MarketData(testnet=testnet, symbol=symbol)
        model = TradingModel(symbol=symbol, testnet=testnet, modelType='bollinger', marketData=_data, pdObserve=pd_ob, pdEstimate=pd_es, orderSize=portfolio.orderSize)
        model.build_initial_input()
        only_pos = 'BOTH'
        if symbol in portfolio.locks['BUY']:
            model.add_signal_lock(slock='BUY')
            only_pos = 'SELL ONLY'
        elif symbol in portfolio.locks['SELL']:
            model.add_signal_lock(slock='SELL')
            only_pos = 'BUY ONLY'
        models[symbol] = model
        print_('\tFinish generating model for %s - positions: %s' % (symbol, only_pos), fileout)

    print_('\n' + barstr('Start Data Streaming', length=100, space_size=5) + '\n', fileout)
    header_print(testnet, client, portfolio, fileout)
    print('\n\tPre-processing Time = %f' % (time.time() - start_time))

    print_('\nStream updating for {} minutes...'.format(pd_ob*min_in_candle), fileout)
    signals = wss_run(portfolio, client, testnet, ['@kline_1m'], models, fileout)

    session_summary(signals, fileout)
    print_('\n\tLocal Time at Close: %s ' % timestr(time.time()*1000), fileout)
    
    print_(barstr(text='Elapsed time = {} seconds'.format(round(time.time()-start_time,2))), fileout)
    print_(barstr(text="", space_size=0), fileout)
    os._exit(1)

def header_print(testnet, client, portfolio, file):
    '''
    Print general information of the trading session
    '''
    t_server, t_local = client.timestamp(), time.time()*1000
    print_('\tTestnet: %s' % str(testnet), file)
    print_('\tServer Time at Start: %s' % timestr(t_server), file)
    print_('\tLocal Time at Start: %s, \tOffset (local-server): %d ms\n' % (timestr(t_local), (t_local-t_server)), file)
    print_('\t#LONG order : %d \t#SHORT order: %d \tOrder Size : %1.2f \n' % (portfolio.equityDist['BUY'], portfolio.equityDist['SELL'], portfolio.orderSize), file)
    try:
        bal_st = pd.DataFrame(client.balance())
        bal_st['updateTime'] = [timestr(b) for b in bal_st['updateTime']]
        print_('\nBeginning Balance Info: \n', file)
        print_(bal_st, file)
    except Exception:
         print_('\nFail to connect to client.balance: \n', file)
    
def session_summary(signals, file):
    '''
    Print summary statistics of the trading session
    '''
    gross_profit = 0
    gross_loss = 0
    win, loss, inpos = 0, 0, 0
    exp_signal = 0
    trade_time = 0
    for symbol in signals:
        for sig in signals[symbol]:
            if sig.is_expired(): exp_signal += 1
            elif sig.is_closed():           
                if sig.clsPrice is not None:
                    if sig.side=='BUY': _side = 1.0
                    elif sig.side=='SELL': _side = -1.0
                    pnl = _side*sig.get_quantity()*(sig.clsPrice - sig.excPrice)
                    trade_time += (sig.clsTime - sig.excTime)/(60*1000)
                    if pnl > 0: 
                        win += 1
                        gross_profit += pnl
                    if pnl <= 0:
                        loss += 1
                        gross_loss += pnl
                else:
                    inpos += 1
    if (win+loss) > 0: timeAv = trade_time/(win+loss)
    else: timeAv = 0.0
    print_( '\n####################\tTrading Session Summary\t####################\n', file)
    print_( '\n\tGross Profit: \t%1.5f' % gross_profit, file)
    print_( '\tGross Loss: \t%1.5f' % gross_loss, file)
    print_( '\tNet Profit: \t%1.5f' % (gross_profit+gross_loss), file)
    print_( '\tAverage time in position: \t%1.2f' % timeAv, file)
    print_( '\tNumber of win trades: \t%d' % win, file)
    print_( '\tNumber of loss trades: \t%d' % loss, file)
    print_( '\tNumber of unfinished trades: \t%d' % inpos, file)
    print_( '\tNumber of expired signals: \t%d \n' % exp_signal, file)

if __name__ == '__main__':
    main(sys.argv[1:])
      