# -*- coding: utf-8 -*-
"""
Created on Sat Mar 24 00:16:07 2020

@author: tranl
"""

import time, sys, math
import numpy as np
import pandas as pd
import websocket
import threading
import json

from tradingpy import PRICEPRE, SIDE, Signal
from utility import print_, orderstr, timestr, barstr

def wss_run(*args):
    ### threading functions
    def data_stream(*args):
        '''
        First thread to send subscription to the exchange
        '''
        params = [str.lower(ins) + str(s) for ins in insIds for s in stream]
        print_(params, fileout)
        ws.send(json.dumps({"method": "SUBSCRIBE", "params": params, "id": 1 }))
        t1_idx = 0
        while len(endFlag)==0:
            if len(SymKlns[insIds[0]]) % 5 == 0 and len(SymKlns[insIds[0]]) > t1_idx and len(SymKlns[insIds[0]]) < models[insIds[0]].pdObserve:
                client.keepalive_stream()
                t1_idx = len(SymKlns[insIds[0]])
            
    def strategy(*args):
        '''
        Second thread to generate signals upon the message from the exchange
        '''
        t2_idx = {}
        for symbol in insIds:
            t2_idx[symbol] = 0
        while len(endFlag)==0 and len(SymKlns[insIds[0]]) < models[insIds[0]].pdObserve:
            try:
                for symbol in insIds:
                    sym_ = SymKlns[symbol].copy()
                    if len(sym_) > t2_idx[symbol]:
                        if models[symbol].modelType == 'bollinger':
                            data_ob = pd.DataFrame(sym_)
                            model_sig = models[symbol].get_last_signal(dataObserve=data_ob) 
                        else: model_sig = None
                        if model_sig is not None:
                            ready = True
                            if ready:
                                side, positionSide, startTime = model_sig['side'], model_sig['positionSide'], model_sig['_t']+60*1000
                                expTime, price = startTime + 5*60*1000, round(model_sig['_p'], PRICEPRE[symbol]) #
                                stopLoss = model_sig['atr']
                                takeProfit = model_sig['atr']
                                new_sig = Signal(symbol=symbol, side=side, size=models[symbol].orderSize, orderType='LIMIT', positionSide=positionSide, price=price, startTime=startTime, expTime=expTime, \
                                             stopLoss=stopLoss, takeProfit=takeProfit, timeLimit=models[symbol].pdEstimate*60, timeInForce='GTC')
                                if in_possition_(Signals[symbol], side='BOTH') or position_count(insIds, Signals, side=side) >= portfolio.equityDist[side]:
                                    new_sig.set_expired()
                                else:
                                    for sig in Signals[symbol]:
                                        if sig.is_waiting():
                                            sig.set_expired()
                                            print_('\n\tSet WAITING signal EXPIRED: \n\t' + str(sig), fileout)
                                Signals[symbol].append(new_sig)
                                print_('\n\tFOUND ' + str(new_sig), fileout)
                        t2_idx[symbol] = len(sym_)
            except Exception:
                print_('\n\tClose on strategy()', fileout)
                ws.close()

    def book_manager(*args):
        '''
        Third thread to excecute/cancel/track the signals generated in strategy()
        '''
        while len(endFlag)==0 and len(SymKlns[insIds[0]]) < models[insIds[0]].pdObserve:
            try:
                time.sleep(1)
                for symbol in insIds:
                    in_position = False
                    last_signal = None
                    for sig in Signals[symbol]:
                        model = models[symbol]
                        sv_time = client.timestamp()
                        if sig.is_waiting():
                            ### Check for EXPIRED order here ###
                            if sv_time > sig.expTime:
                                sig.set_expired()
                                print_('\n\tSet WAITING signal EXPIRED: \n\t' + str(sig), fileout)
                            else:
                                last_signal = sig

                        elif sig.is_ordered():
                            ### Set ACTIVE order here ###
                            in_position = True
                            order_update = client.query_order(symbol, sig.orderId)
                            if order_update['status'] == 'FILLED':
                                sig.set_active(excTime=order_update['updateTime'], excPrice=order_update['avgPrice'], excQty=order_update['executedQty'])                 
                                sig.path_update(lastTime=sig.excTime, lastPrice=sig.excPrice) 
                                print_('\n\tSet BOOKED order ACTIVE: \n\t' + str(sig) + '\n\t' + orderstr(order_update), fileout)

                            ### PROBLEM 3 Insert your code to handle EXPIRED and PARTIALLY_FILLED order here ###
                            elif sv_time > order_update['updateTime'] + 60*1000:
                                if order_update['status'] == 'PARTIALLY_FILLED':
                                    client.cancel_order(symbol, sig.orderId)
                                    sig.set_active(excTime=order_update['updateTime'], excPrice=order_update['avgPrice'], excQty=order_update['executedQty'])
                                    sig.path_update(lastTime=sig.excTime, lastPrice=sig.excPrice)
                                    print_('\n\tSet BOOKED order ACTIVE: \n\t' + str(sig) + '\n\t' + orderstr(order_update), fileout)
                                elif sv_time > order_update['updateTime'] + 2*60*1000:
                                    client.cancel_order(symbol, sig.orderId)
                                    sig.set_expired()
                                    order_update = client.query_order(symbol, sig.orderId)
                                    print_('\n\tSet BOOKED order EXPIRED: \n\t' + str(sig) + '\n\t' + orderstr(order_update), fileout)

                        elif sig.is_active():
                            ### Control ACTIVE position here ###
                            in_position = True
                            recent_trades = model.marketData.recent_trades(limit=5)
                            for trade in recent_trades:
                                if int(trade['time']) > sig.pricePath[-1]['timestamp']:
                                    sig.path_update(lastTime=trade['time'], lastPrice=trade['price'])
                            exit_sign, pos = sig.exit_triggers()
                            if exit_sign:
                                print_('\n\tFound ' + str(exit_sign) + '{}\n'.format(round(pos,4)), fileout)
                                cnt_order = sig.counter_order()
                                order = client.new_order(symbol=symbol, side=cnt_order['side'], orderType='MARKET', quantity=cnt_order['amt'], positionSide=sig.positionSide) #, timeInForce=cnt_order['TIF'], price=lim)
                                sig.set_cnt_ordered(cntorderId=order['orderId'], cntType='MARKET', cntTime=order['updateTime'])
                                print_('\tPlaced COUNTER order: \n\t' + str(sig) + '\n\t' + orderstr(order), fileout)

                        elif sig.is_cnt_ordered():
                            ### Set CLOSED position here ###
                            in_position = True
                            order_update = client.query_order(symbol, sig.cntorderId)
                            if order_update['status'] == 'FILLED':
                                sig.set_closed(clsTime=order_update['updateTime'], clsPrice=order_update['avgPrice'])
                                print_('\n\tClosed order: \n\t' + str(sig) + '\n\t' + orderstr(order_update), fileout)

                    if (not in_position) and (last_signal is not None):
                        ### Check for ENTRY and place NEW order here ###
                        sig = last_signal
                        if sig.orderType == 'MARKET':
                            order  = client.new_order(symbol=symbol, side=sig.side, orderType=sig.orderType, quantity=sig.get_quantity(), positionSide=sig.positionSide)
                            sig.set_ordered(orderId=order['orderId'], orderTime=order['updateTime'], limitPrice=None)
                            print_('\n\tPlaced NEW order: \n\t' + str(sig) + '\n\t' + orderstr(order), fileout)
                        elif sig.orderType=='LIMIT':
                            bids, asks, lim = get_possible_price(model.marketData, sig.side)
                            if lim is not None and (lim < sig.price*1.01 and lim > sig.price*0.99):
                                order = client.new_order(symbol=symbol, side=sig.side, orderType=sig.orderType, quantity=sig.get_quantity(), positionSide=sig.positionSide, timeInForce='GTC', price=lim)
                                sig.set_ordered(orderId=order['orderId'], orderTime=order['updateTime'], limitPrice=lim)
                                print_('\n\tPlaced NEW order: \n\t' + str(sig) + '\n\t' + orderstr(order), fileout)
            except Exception:
                print_('\n\tClose on book_manager()', fileout)
                ws.close()
        ws.close()
    
    ### websocket functions
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
                print_( '%d. %s\t' % (len(SymKlns[symbol]), symbol) + timestr(new_kln['_t']) + '\t' + \
                        ''.join(['{:>3}:{:<10}'.format(k, v) for k,v in iter(new_kln.items()) if not k=='_t']), fileout)

    def on_error(ws, error):
        '''
        Do something when websocket has an error
        '''
        print_(error, fileout)
        return

    def on_close(ws):
        '''
        Do something when websocket closes
        '''
        endFlag.append(1)
        for t in [t1, t2, t3]: t.join()
        return

    def on_open(ws, *args):
        '''
        Start multi-threading functions
        '''
        t1.start()
        t2.start()
        t3.start()
        return

    def position_count(insIds, signal_list, side='BOTH'):
        '''
        Returns number of open positions
        '''
        count = 0
        for s in insIds:
            for sig in signal_list[s]:
                if sig.side==side or side=='BOTH':
                    if sig.is_ordered() or sig.is_active() or sig.is_cnt_ordered():
                        count += 1
        return count

    def in_possition_(signal_list, side='BOTH'):
        '''
        Check if there is any open positions
        '''
        in_pos = False
        for sig in signal_list:
            if sig.side==side or side=='BOTH':
                if sig.is_ordered() or sig.is_active() or sig.is_cnt_ordered():
                    in_pos = True
                    break
        return in_pos

    def get_possible_price(mk_data, side):
        '''
        Return a safe limit price available on the market
        '''
        mk_depth = mk_data.order_book(limit=5)
        bids = list(float(x[0]) for x in mk_depth['bids'])
        asks = list(float(x[0]) for x in mk_depth['asks'])
        try:
            lim = (side=='BUY')*(bids[0]+bids[1])/2 + (side=='SELL')*(asks[0]+asks[1])/2
            lim = round(lim, PRICEPRE[mk_data.symbol.upper()])
        except:
            lim = None
        return bids, asks, lim

    start_time = time.time()
    portfolio, client, testnet, stream, models, fileout = args
    insIds = portfolio.tradeIns
    SymKlns = {}
    Signals = {}
    for symbol in insIds:
       SymKlns[symbol] = []
       Signals[symbol] = []
       
    endFlag = []
    t1 = threading.Thread(target=data_stream)
    t2 = threading.Thread(target=strategy)
    t3 = threading.Thread(target=book_manager) 
    listen_key = client.get_listen_key()
    ws = websocket.WebSocketApp(f'{client.wss_way}{listen_key}',
                                on_message=on_message, 
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()
    client.close_stream()
    print_('\n' + barstr('Close Opening Positions', length=100, space_size=5) + '\n', fileout)
    
    ### PROBLEM 2 Insert your code to close all positions here ###
    '''
    Place a COUNTER order at 0.1% take-profit level from the entry price
    '''
    in_position = False
    for symbol in insIds:
        if in_possition_(Signals[symbol]):
            in_position = True
    while in_position:
        for symbol in insIds:
            model = models[symbol]
            for sig in Signals[symbol]:     
                if sig.is_waiting():
                    sig.set_expired()
                    print_('\n\tSet WAITING signal EXPIRED: \n\t' + str(sig), fileout)
                elif sig.is_ordered():
                    client.cancel_order(symbol, sig.orderId)
                    sig.set_expired()
                    order_update = client.query_order(symbol, sig.orderId)
                    print_('\n\tSet BOOKED order EXPIRED: \n\t' + str(sig) + '\n\t' + orderstr(order_update), fileout)
                elif sig.is_active():
                    cnt_order = sig.counter_order()               
                    lim = round(sig.excPrice*(1 + SIDE[sig.side]*0.1/100), PRICEPRE[symbol])
                    order = client.new_order(symbol=symbol, side=cnt_order['side'], orderType='LIMIT', quantity=cnt_order['amt'], positionSide=sig.positionSide, timeInForce=cnt_order['TIF'], price=lim)
                    sig.set_cnt_ordered(cntorderId=order['orderId'], cntType='LIMIT', cntTime=order['updateTime'], cntlimitPrice=lim)
                    print_('\tPlaced COUNTER order: \n\t' + str(sig) + '\n\t' + orderstr(order), fileout)                                                                                 
                elif sig.is_cnt_ordered():
                    order_update = client.query_order(symbol, sig.cntorderId)
                    sig.set_closed(clsTime=order_update['updateTime'], clsPrice=None)
                    print_('\n\tClosed order: \n\t' + str(sig) + '\n\t' + orderstr(order_update), fileout)
        _position = False
        for symbol in insIds:
            if in_possition_(Signals[symbol]):
                _position = True
                break
        in_position = _position     

    return Signals