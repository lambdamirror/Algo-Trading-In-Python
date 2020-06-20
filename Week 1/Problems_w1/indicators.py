import numpy as np
import pandas as pd
import matplotlib.patches as patches

class Renko:
    """ renko price chart transformation """
    def __init__(self):
        self.source_prices = pd.DataFrame(columns=['_t', '_p', '_T'])
        self.renko_prices = pd.DataFrame(columns=['_t', '_p', '_T'])
        self.renko_directions = []
    
    # Setting brick size. Auto mode is preferred, it uses history
    def set_brick_size(self, HLC_history = None, auto = True, brick_size = 10.0):
        if auto == True:
            self.brick_size = self.__get_optimal_brick_size(HLC_history)
        else:
            self.brick_size = brick_size
        return self.brick_size
    
    def __renko_rule(self, last_price):
        # Get the gap between two prices
        gap_div = int(float(last_price['_p'] - self.renko_prices['_p'].iloc[-1]) / self.brick_size)
        is_new_brick = False
        start_brick = 0
        num_new_bars = 0

        # When we have some gap in prices
        if gap_div != 0:
            # Forward any direction (up or down)
            if (gap_div > 0 and (self.renko_directions[-1] > 0 or self.renko_directions[-1] == 0)) or (gap_div < 0 and (self.renko_directions[-1] < 0 or self.renko_directions[-1] == 0)):
                num_new_bars = gap_div
                is_new_brick = True
                start_brick = 0
            # Backward direction (up -> down or down -> up)
            elif np.abs(gap_div) >= 2: # Should be double gap at least
                num_new_bars = gap_div
                num_new_bars -= np.sign(gap_div)
                start_brick = 2
                is_new_brick = True
                self.renko_prices = self.renko_prices.append({'_t': self.renko_prices['_T'].iloc[-1], '_p': self.renko_prices['_p'].iloc[-1] \
                                                             + 2 * self.brick_size * np.sign(gap_div), '_T': last_price['_T']}, ignore_index=True)
                self.renko_directions.append(np.sign(gap_div))
            #else:
                #num_new_bars = 0

            if is_new_brick:
                # Add each brick
                for d in range(start_brick, np.abs(gap_div)):
                    self.renko_prices = self.renko_prices.append({'_t': self.renko_prices['_T'].iloc[-1], '_p': self.renko_prices['_p'].iloc[-1] \
                                                                  + self.brick_size * np.sign(gap_div), '_T': last_price['_T']}, ignore_index=True)
                    self.renko_directions.append(np.sign(gap_div))
        
        return num_new_bars
                
    # Getting renko on history
    def build_history(self, prices):
        if prices.shape[0] > 0:
            # Init by start values
            self.source_prices = prices.copy()
            self.renko_prices = self.renko_prices.append(prices.iloc[0], ignore_index=True)
            self.renko_directions.append(0)
            # For each price in history
            for i in range(1, self.source_prices.shape[0]):
                self.__renko_rule(self.source_prices.iloc[i])
        
        return self.renko_prices.shape[0]
    
    # Getting next renko value for last price
    def do_next(self, last_price):
        if self.renko_prices.shape[0] == 0:
            self.source_prices = self.source_prices.append(last_price, ignore_index=True)
            self.renko_prices = self.renko_prices.append(last_price, ignore_index=True)
            self.renko_directions.append(0)
            return 1
        else:
            self.source_prices = self.source_prices.append(last_price, ignore_index=True)
            return self.__renko_rule(last_price)
    
    # Simple method to get optimal brick size based on ATR
    def __get_optimal_brick_size(self, HLC_history, atr_timeperiod = 60):
        brick_size = 0.0
        
        # If we have enough of data
        if HLC_history.shape[0] > atr_timeperiod:
            df = HLC_history.iloc[-atr_timeperiod:]
            _h_l = df['_h'] - df['_l']
            _h_c = (df['_h'] - df['_c'].shift(1)).abs()
            _l_c = (df['_l'] - df['_c'].shift(1)).abs()
            tr_df = pd.concat([_h_l, _h_c, _l_c], axis=1).dropna().max(axis=1)
            brick_size = tr_df.median()   
        return brick_size

    def evaluate(self, method = 'simple'):
        balance = 0
        sign_changes = 0
        price_ratio = self.source_prices.shape[0] / self.renko_prices.shape[0]

        if method == 'simple':
            for i in range(2, len(self.renko_directions)):
                if self.renko_directions[i] == self.renko_directions[i - 1]:
                    balance = balance + 1
                else:
                    balance = balance - 2
                    sign_changes = sign_changes + 1

            if sign_changes == 0:
                sign_changes = 1

            score = balance / sign_changes
            if score >= 0 and price_ratio >= 1:
                score = np.log(score + 1) * np.log(price_ratio)
            else:
                score = -1.0

            return {'balance': balance, 'sign_changes:': sign_changes, 
                    'price_ratio': price_ratio, 'score': score}
    
    def get_prices(self):
        return self.renko_prices
    
    def get_directions(self):
        return self.renko_directions
    
    def plot_renko(self, ax, col_up = 'g', col_down = 'r'): 
        # Plot each renko bar
        for i in range(1, self.renko_prices.shape[0]):
            # Set basic params for patch rectangle
            col = col_up if self.renko_directions[i] == 1 else col_down
            x = i
            y = self.renko_prices['_p'].iloc[i] - self.brick_size if self.renko_directions[i] == 1 else self.renko_prices['_p'].iloc[i]
            height = self.brick_size
                
            # Draw bar with params
            ax.add_patch(
                patches.Rectangle(
                    (x, y),   # (x,y)
                    1.0,     # width
                    self.brick_size, # height
                    facecolor = col
                )
            )
        return ax

def mean_test(df, feat=None, alpha=0.1):
    '''
    Returns Dicky-Fuller test
    '''
    if feat is None: _df = df
    else: _df = df[feat]
    _mean_rv = (adfuller(_df)[1] < alpha)
    if not _mean_rv:
        return False
    return True
        
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