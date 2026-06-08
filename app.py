from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import time

app = Flask(__name__)
CORS(app)

def get_signal(rs, above_ema, phase):
    if rs >= 60 and above_ema and phase in ['Accumulation', 'Markup']:
        return 'strong'
    elif rs >= 45 and above_ema:
        return 'watch'
    else:
        return 'avoid'

def get_smc_phase(hist):
    if len(hist) < 50:
        return 'Congestion'
    close = hist['Close']
    recent = close.iloc[-20:]
    prev = close.iloc[-40:-20]
    recent_high = recent.max()
    recent_low = recent.min()
    prev_high = prev.max()
    prev_low = prev.min()
    if recent_low > prev_low and recent_high > prev_high:
        return 'Markup'
    elif recent_low > prev_low and recent_high <= prev_high:
        return 'Accumulation'
    elif recent_high < prev_high and recent_low < prev_low:
        return 'Distribution'
    else:
        return 'Congestion'

def calc_rs(hist, period=90):
    if len(hist) < period:
        return 50
    start = hist['Close'].iloc[-period]
    end = hist['Close'].iloc[-1]
    if start == 0:
        return 50
    change = ((end - start) / start) * 100
    rs = min(max(int(50 + change), 0), 100)
    return rs

def fetch_stock(sym):
    try:
        ticker = yf.Ticker(sym + '.NS')
        hist = ticker.history(period='6mo')
        if hist.empty:
            return {'symbol': sym, 'error': 'No data found', 'signal': 'avoid'}
        close = float(hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else close
        chg_pct = round(((close - prev_close) / prev_close) * 100, 2)
        ema200_series = hist['Close'].ewm(span=200, adjust=False).mean()
        ema200 = float(ema200_series.iloc[-1])
        above_ema = close > ema200
        rs = calc_rs(hist)
        phase = get_smc_phase(hist)
        signal = get_signal(rs, above_ema, phase)
        volume = int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
        return {
            'symbol': sym,
            'price': round(close, 2),
            'chgPct': chg_pct,
            'rs': rs,
            'aboveEMA': above_ema,
            'ema200': round(ema200, 2),
            'phase': phase,
            'signal': signal,
            'volume': volume
        }
    except Exception as e:
        return {'symbol': sym, 'error': str(e), 'signal': 'avoid'}

@app.route('/')
def home():
    return jsonify({'status': 'MITS 360 Alpha Harvester API Live!'})

@app.route('/scan')
def scan():
    symbols_raw = request.args.get('symbols', '')
    if not symbols_raw:
        return jsonify({'error': 'No symbols provided'}), 400

    symbols = [s.strip().upper() for s in symbols_raw.split(',') if s.strip()]
    results = []

    for i, sym in enumerate(symbols):
        result = fetch_stock(sym)
        results.append(result)
        # Delay between requests to avoid Yahoo Finance rate limiting
        if i < len(symbols) - 1:
            time.sleep(1.5)

    return jsonify({'results': results, 'count': len(results)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
