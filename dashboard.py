# dashboard.py
import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go

# --- CONFIGURATION ---
st.set_page_config(page_title="Stock Market Dashboard", layout="wide")

# --- API & DATA FETCHING ---
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def get_stock_data(api_key, symbol):
    """Fetches intraday stock data from Alpha Vantage."""
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": "5min",
        "apikey": api_key,
        "outputsize": "full"
    }
    try:
        response = requests.get("https://www.alphavantage.co/query", params=params)
        response.raise_for_status()
        data = response.json()
        if "Time Series (5min)" not in data:
            st.error(f"Could not retrieve data for symbol '{symbol}'. Check the symbol or API key.")
            return pd.DataFrame()
        
        df = pd.DataFrame.from_dict(data["Time Series (5min)"], orient='index')
        df = df.rename(columns={
            '1. open': 'Open', '2. high': 'High', 
            '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'
        })
        df.index = pd.to_datetime(df.index)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col])
        return df.sort_index()
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}")
        return pd.DataFrame()

# --- FINANCIAL INDICATORS ---
def calculate_sma(data, window):
    """Calculates Simple Moving Average."""
    return data['Close'].rolling(window=window).mean()

def calculate_rsi(data, window=14):
    """Calculates Relative Strength Index."""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- UI & DASHBOARD ---
st.title("Real-Time Stock Market Dashboard")

# Sidebar for user inputs
st.sidebar.header("Settings")
api_key = st.sidebar.text_input("Enter your Alpha Vantage API Key", type="password")
symbol = st.sidebar.text_input("Stock Symbol", "MSFT").upper()

chart_type = st.sidebar.selectbox("Chart Type", ["Candlestick", "Line"])
sma_short_window = st.sidebar.slider("Short-term SMA", 5, 50, 20)
sma_long_window = st.sidebar.slider("Long-term SMA", 50, 200, 50)

if not api_key:
    st.warning("Please enter your Alpha Vantage API key in the sidebar to start.")
    st.stop()

# Main content
data = get_stock_data(api_key, symbol)

if not data.empty:
    # Calculate indicators
    data['SMA_Short'] = calculate_sma(data, sma_short_window)
    data['SMA_Long'] = calculate_sma(data, sma_long_window)
    data['RSI'] = calculate_rsi(data)

    # Display latest metrics
    latest_data = data.iloc[-1]
    prev_close = data.iloc[-2]['Close']
    price_change = latest_data['Close'] - prev_close
    price_change_pct = (price_change / prev_close) * 100

    col1, col2, col3 = st.columns(3)
    col1.metric(f"Last Price ({symbol})", f"${latest_data['Close']:.2f}", f"{price_change:.2f} ({price_change_pct:.2f}%)")
    col2.metric("Day High", f"${data['High'].max():.2f}")
    col3.metric("Day Low", f"${data['Low'].min():.2f}")

    # Main Price Chart
    fig_price = go.Figure()

    if chart_type == "Candlestick":
        fig_price.add_trace(go.Candlestick(x=data.index,
                                           open=data['Open'],
                                           high=data['High'],
                                           low=data['Low'],
                                           close=data['Close'],
                                           name='Price'))
    else:
        fig_price.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Close Price'))

    fig_price.add_trace(go.Scatter(x=data.index, y=data['SMA_Short'], mode='lines', name=f'SMA {sma_short_window}', line=dict(color='orange')))
    fig_price.add_trace(go.Scatter(x=data.index, y=data['SMA_Long'], mode='lines', name=f'SMA {sma_long_window}', line=dict(color='purple')))
    
    fig_price.update_layout(
        title=f'{symbol} Price Chart',
        yaxis_title='Price (USD)',
        xaxis_rangeslider_visible=False
    )
    st.plotly_chart(fig_price, use_container_width=True)

    # RSI Chart
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=data.index, y=data['RSI'], mode='lines', name='RSI'))
    fig_rsi.update_layout(
        title='Relative Strength Index (RSI)',
        yaxis_title='RSI',
        yaxis=dict(range=[0, 100])
    )
    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
    st.plotly_chart(fig_rsi, use_container_width=True)

    # Data Table
    with st.expander("View Raw Data"):
        st.dataframe(data.sort_index(ascending=False))

else:
    st.info("Waiting for valid API key and symbol...")

