import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. Supabase 設定 ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 獲取資產配置 ---
@st.cache_data(ttl=600)
def get_asset_configs():
    try:
        response = supabase.table("asset_configs").select("symbol, contract_size").execute()
        return {item['symbol']: float(item['contract_size']) for item in response.data}
    except Exception as e:
        st.error(f"讀取資產配置失敗: {e}")
        return {"XAUUSD": 100.0}

asset_map = get_asset_configs()

# --- 2. 頁面配置 ---
st.set_page_config(page_title="Alan's Trading SOP", layout="wide")
st.title("🛡️ Alan 交易紀律守門員 (Supabase 版)")

tab1, tab2 = st.tabs(["🆕 新建交易計畫", "📊 歷史複盤"])

# ==========================================
# TAB 1: 新建交易計畫
# ==========================================
with tab1:
    st.subheader("1. 交易基礎與風控計算")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        symbol = st.selectbox("資產 (Asset)", options=list(asset_map.keys()))
        direction = st.radio("方向", ["做多", "做空"], horizontal=True)
        timeframe = st.selectbox("入場時間框架", ["30MINS", "1HR", "2HR", "4HR", "DAY"])
        strategy_type = st.selectbox("順勢/逆勢", ["順勢", "逆勢"])

    with col2:
        entry_price = st.number_input("買入價 (Entry)", value=0.0, format="%.5f")
        tp_price = st.number_input("止盈價 (TP)", value=0.0, format="%.5f")
        sl_price = st.number_input("止損價 (SL)", value=0.0, format="%.5f")

    # --- Validation 邏輯檢查 ---
    validation_passed = True
    error_msg = ""
    if entry_price > 0:
        if direction == "做多":
            if not (tp_price > entry_price):
                error_msg = "❌ [做多錯誤] TP 必須大於買入價"; validation_passed = False
            elif not (sl_price < entry_price):
                error_msg = "❌ [做多錯誤] SL 必須小於買入價"; validation_passed = False
        else: # 做空
            if not (tp_price < entry_price):
                error_msg = "❌ [做空錯誤] TP 必須小於買入價"; validation_passed = False
            elif not (sl_price > entry_price):
                error_msg = "❌ [做空錯誤] SL 必須大於買入價"; validation_passed = False

    with col3:
        capital = st.number_input("當前本金 (USD)", value=10000.0)
        risk_pct = st.slider("風險比例 (%)", 0.5, 3.0, 1.5, step=0.1)
        if not validation_passed: st.error(error_msg)
        
        # --- 計算核心邏輯 ---
        current_contract_size = asset_map.get(symbol, 1.0)
        sl_dist, tp_dist = abs(entry_price - sl_price), abs(tp_price - entry_price)
        lot_size, profit_usd, loss_usd, rr = 0.0, 0.0, 0.0, 0.0
        
        if validation_passed and sl_dist > 0:
            loss_usd = capital * (risk_pct / 100)
            lot_size = loss_usd / (sl_dist * current_contract_size)
            profit_usd = tp_dist * current_contract_size * lot_size
            rr = profit_usd / loss_usd if loss_usd > 0 else 0
            
            c_lot, c_rr = st.columns(2)
            c_lot.metric(f"建議手數", f"{lot_size:.2f}")
            c_rr.metric("預期 RR", f"1:{rr:.2f}")
            cw, cl = st.columns(2)
            cw.metric("💰 預期獲利", f"${profit_usd:.2f}", delta=f"{rr:.2f}R")
            cl.metric("📉 預期虧損", f"-${loss_usd:.2f}", delta="-1.0R", delta_color="inverse")
        
    st.divider()
    st.subheader("2. 技術條件確認 (Confluences)")
    c1, c2, c3, c4 = st.columns(4)
    with c1: trend_status = st.multiselect("走勢", ["上升趨勢", "下跌趨勢", "橫行"])
    with c2: patterns = st.multiselect("形態", ["雙頂", "雙底", "頭肩頂/底", "V形反轉", "通道", "三角形", "旗形", "CUP WITH HANDLE"])
    with c3: conditions = st.multiselect("條件", ["前頂/底", "通道中軸", "DSO動能", "DSO動能背馳", "黃金比率0.382", "黃金比率0.618"])
    with c4: candlesticks = st.multiselect("陰陽燭", ["大陽/大陰", "槌頭", "早晨/黃昏星", "孕線", "吞沒", "平頭頂/底"])

    st.divider()
    st.subheader("3. 交易心態與想法")
    emotions = st.multiselect("當前感受", ["焦慮", "興奮", "FOMO", "冷靜理性", "報復模式", "平常心", "緊張"])
    mental_score = st.select_slider("心理穩定度", options=[1, 2, 3, 4, 5], value=5)
    remarks = st.text_area("REMARKS")

    submit_btn = st.button("🚀 確認執行交易並存入 Supabase", disabled=not validation_passed)
    if submit_btn:
        trade_data = {
            "symbol": symbol, "direction": direction, "timeframe": timeframe,
            "entry_price": entry_price, "tp_price": tp_price, "sl_price": sl_price,
            "lot_size": round(lot_size, 2), "rr_ratio": round(rr, 2),
            "expected_profit_usd": round(profit_usd, 2), "expected_loss_usd": round(loss_usd, 2),
            "setup_logic": {"strategy": strategy_type, "trend": trend_status, "patterns": patterns},
            "confluence": {"indicators": conditions, "candlesticks": candlesticks},
            "psychology": {"emotions": emotions, "score": mental_score},
            "remarks": remarks, "status": "Open"
        }
        try:
            supabase.table("trading_journal").insert(trade_data).execute()
            st.balloons(); st.success(f"✅ 交易已成功存入！")
        except Exception as e: st.error(f"❌ 寫入失敗: {e}")

# ==========================================
# TAB 2: 歷史複盤
# ==========================================
with tab2:
    st.title("📊 交易績效診斷 Dashboard")
    try:
        response = supabase.table("trading_journal").select("*").order("created_at", desc=True).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            
            # --- 數據清洗 ---
            num_cols = ['expected_profit_usd', 'expected_loss_usd', 'entry_price', 'sl_price', 'tp_price']
            for col in num_cols:
                if col in df.columns: df[col] = pd.to_numeric(df[col]).fillna(0)
            
            df['score'] = df['psychology'].apply(lambda x: x.get('score', 3) if isinstance(x, dict) else 3)
            df['emotions_list'] = df['psychology'].apply(lambda x: ", ".join(x.get('emotions', [])) if isinstance(x, dict) else "N/A")
            
            # 排序與資金曲線
            df = df.sort_values('created_at')
            df['equity'] = 10000 + df['expected_profit_usd'].cumsum()
            
            # --- 進階 KPI 計算 ---
            total_trades = len(df)
            wins_df, loss_df = df[df['expected_profit_usd'] > 0], df[df['expected_profit_usd'] < 0]
            win_rate = (len(wins_df) / total_trades * 100) if total_trades > 0 else 0
            
            avg_profit = wins_df['expected_profit_usd'].mean() if len(wins_df) > 0 else 0
            avg_loss = abs(loss_df['expected_profit_usd'].mean()) if len(loss_df) > 0 else 1
            
            profit_factor = wins_df['expected_profit_usd'].sum() / abs(loss_df['expected_profit_usd'].sum()) if loss_df['expected_profit_usd'].sum() != 0 else 0
            avg_rr = avg_profit / avg_loss if avg_loss > 0 else 0
            
            pnl_std = df['expected_profit_usd'].std()
            sharpe = (df['expected_profit_usd'].mean() / pnl_std * np.sqrt(252)) if pnl_std > 0 else 0

            # --- 第一層：KPI 顯示 ---
            st.subheader("📈 第一層：績效總覽")
            r1c1, r1c2, r1c3 = st.columns(3)
            r2c1, r2c2, r2c3 = st.columns(3)
            
            r1c1.metric("交易次數", f"{total_trades}")
            r1c2.metric("勝率", f"{win_rate:.1f}%")
            r1c3.metric("Profit Factor", f"{profit_factor:.2f}")
            r2c1.metric("平均獲利", f"${avg_profit:.2f}")
            r2c2.metric("平均虧損", f"-${avg_loss:.2f}")
            r2c3.metric("平均實際 RR", f"1:{avg_rr:.2f}")
            
            st.write(f"🛡️ **Sharpe Ratio (年化):** `{sharpe:.2f}`")

            # --- 圖表展示 ---
            st.plotly_chart(px.line(df, x='created_at', y='equity', title="資金曲線", template="plotly_dark").update_traces(line_color='#00FFCC'), width='stretch')

            col_l, col_r = st.columns(2)
            with col_l:
                asset_pnl = df.groupby('symbol')['expected_profit_usd'].sum().sort_values()
                st.plotly_chart(px.bar(asset_pnl, orientation='h', title="資產盈虧貢獻", template="plotly_dark", color=asset_pnl.values, color_continuous_scale='RdYlGn'), width='stretch')

            with col_r:
                df['rr_group'] = (df['expected_profit_usd'] / df['expected_loss_usd'].abs()).round(1)
                rr_stats = df.groupby('rr_group').agg(count=('expected_profit_usd', 'count'), win_rate=('expected_profit_usd', lambda x: (x > 0).mean() * 100)).reset_index()
                fig_rr = go.Figure()
                fig_rr.add_trace(go.Bar(x=rr_stats['rr_group'], y=rr_stats['count'], name="次數", yaxis='y1'))
                fig_rr.add_trace(go.Scatter(x=rr_stats['rr_group'], y=rr_stats['win_rate'], name="勝率%", yaxis='y2', line=dict(color='orange')))
                fig_rr.update_layout(title="不同 RR 下的表現", yaxis=dict(title="次數"), yaxis2=dict(title="勝率%", overlaying='y', side='right', range=[0, 100]), template="plotly_dark")
                st.plotly_chart(fig_rr, width='stretch')

            st.divider()
            st.subheader("🧠 心理因素診斷")
            df['bubble_size'] = df['expected_loss_usd'].abs().replace(0, 1)
            st.plotly_chart(px.scatter(df, x="score", y="expected_profit_usd", color="symbol", size="bubble_size", hover_data=["emotions_list", "remarks"], template="plotly_dark", title="心理穩定度 vs 盈虧"), width='stretch')

        else: st.info("📭 尚無數據。")
    except Exception as e: st.error(f"❌ 載入失敗: {e}")