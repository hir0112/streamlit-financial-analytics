import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib
import requests
import json
import os
from dotenv import load_dotenv
import datetime
from dateutil.relativedelta import relativedelta

# .envファイルをロード
load_dotenv()

# 環境変数を読み込む
mail_address = os.getenv("MAIL_ADDRESS")
password = os.getenv("PASSWORD")

data = {"mailaddress": mail_address, "password": password}

# リフレッシュトークンを取得 (キャッシュの有効期間は1週間)
@st.cache_data(ttl=604800)
def get_refresh_token(data):
    r_post = requests.post("https://api.jquants.com/v1/token/auth_user", data=json.dumps(data))
    return r_post.json()["refreshToken"]

REFRESH_TOKEN = get_refresh_token(data)

# IDトークンを取得 (キャッシュの有効期間は24時間)
@st.cache_data(ttl=86400)
def get_id_token(refresh_token):
    r_post = requests.post(f"https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}")
    return r_post.json()["idToken"]

ID_TOKEN = get_id_token(REFRESH_TOKEN)

# 認証ヘッダーを作成
headers = {"Authorization": "Bearer {}".format(ID_TOKEN)}

# ------------------------

# フィルタリング機能を表示
col1, col2 = st.columns([1, 2])

# 銘柄コードを入力する機能
with col1:
    security_code = st.number_input(
        "銘柄コードを入力", 
        min_value=1000, max_value=9999, 
        step=1, value=7974, 
        format="%d"
        )
    st.markdown(f"[{'銘柄コードを検索'}]({'https://quote.jpx.co.jp/jpx/template/quote.cgi?F=tmp/stock_search'})")
    
# 検索可能な期間を動的に計算 {検索可能データは過去2年分 (12週間遅延) のため}
def calculate_search_period():
    today = datetime.date.today()                   # 今日の日付
    end_date = today - relativedelta(weeks=12)      # 12週間前の日付
    start_date = end_date - relativedelta(years=2)  # 12週間前から起算して、2年前の日付
    return start_date, end_date
  
# 検索期間を選択する機能
with col2:
    default_start_date, default_end_date = calculate_search_period()
    inputed_start_date, inputed_end_date = st.date_input(
        "検索期間を選択",
        value = (default_start_date, default_end_date),
        min_value = default_start_date,
        max_value = default_end_date
    )
    st.caption("ℹ 検索可能データは**過去2年分** (12週間遅延)")

st.write("")
st.write("")

# ------------------------

# 会社情報を取得
@st.cache_data
def get_info(security_code, inputed_end_date, headers):
    r = requests.get(f"https://api.jquants.com/v1/listed/info?code={security_code}&date={inputed_end_date}", headers=headers)
    return pd.DataFrame(r.json()["info"])

info = get_info(security_code, inputed_end_date, headers)

# 会社情報を表示
st.write("""#### 会社情報""")
st.caption(f"ℹ **{info['Date'][0]}** 時点")

summarized_info = info[["Code", "CompanyName", "CompanyNameEnglish", "Sector17CodeName", "Sector33CodeName", "ScaleCategory", "MarketCodeName"]]
summarized_info = summarized_info.rename(columns={"Code":"銘柄コード", "CompanyName":"会社名", "CompanyNameEnglish":"会社名 (英語)", "Sector17CodeName":"17業種区分", "Sector33CodeName":"33業種区分", "ScaleCategory":"規模区分", "MarketCodeName":"市場区分"})
st.dataframe(summarized_info, hide_index=True)
st.write("")

# ------------------------

# 株価四本値を取得
@st.cache_data
def get_daily_quotes(security_code, inputed_start_date, inputed_end_date, headers):
    r = requests.get(f"https://api.jquants.com/v1/prices/daily_quotes?code={security_code}&from={inputed_start_date}&to={inputed_end_date}", headers=headers)
    return pd.DataFrame(r.json()["daily_quotes"])

daily_quotes = get_daily_quotes(security_code, inputed_start_date, inputed_end_date, headers)

# 株価四本値を表示
st.write("""#### 株価の推移""")
# st.write("###### * 株価は分割・併合を考慮した調整済み株価")
st.markdown("<span style='font-size: 15px'>* 株価は分割・併合を考慮した調整済み株価</span>", unsafe_allow_html=True)
st.caption(f"ℹ **{inputed_start_date}** - **{inputed_end_date}** の期間を表示")
st.write("")
st_trends = daily_quotes.set_index("Date")[["AdjustmentOpen", "AdjustmentHigh", "AdjustmentLow", "AdjustmentClose"]]
st_trends = st_trends.rename(columns={"AdjustmentOpen":"始値", "AdjustmentHigh":"高値", "AdjustmentLow":"安値", "AdjustmentClose":"終値"})
st.line_chart(st_trends)

# ------------------------

# 財務情報を取得
@st.cache_data
def get_statements(security_code, headers):
    r = requests.get(f"https://api.jquants.com/v1/fins/statements?code={security_code}", headers=headers)
    return pd.DataFrame(r.json()["statements"])

statements = get_statements(security_code, headers)

statements["DisclosedDate"] = statements["DisclosedDate"]                                                          # 開示日
statements["TypeOfCurrentPeriod"] = statements["TypeOfCurrentPeriod"]                                              # 当会計期間の種類
statements["CurrentPeriodEndDate"] = statements["CurrentPeriodEndDate"]                                            # 当会計期間終了日
statements["NetSales"] = statements["NetSales"].replace("", np.nan).astype(float)                                  # 売上高
statements["ForecastNetSales"] = statements["ForecastNetSales"].replace("", np.nan).astype(float)                  # 売上高_予想_期末
statements["OperatingProfit"] = statements["OperatingProfit"].replace("", np.nan).astype(float)                    # 営業利益
statements["ForecastOperatingProfit"] = statements["ForecastOperatingProfit"].replace("", np.nan).astype(float)    # 営業利益_予想_期末
statements["Profit"] = statements["Profit"].replace("", np.nan).astype(float)                                      # 当期純利益
statements["ForecastProfit"] = statements["ForecastProfit"].replace("", np.nan).astype(float)                      # 当期純利益_予想_期末
statements["EarningsPerShare"] = statements["EarningsPerShare"].replace("", np.nan).astype(float)                  # 一株あたり当期純利益
statements["ForecastEarningsPerShare"] = statements["ForecastEarningsPerShare"].replace("", np.nan).astype(float)  # 一株あたり当期純利益_予想_期末
statements["TotalAssets"] = statements["TotalAssets"].replace("", np.nan).astype(float)                            # 総資産
statements["Equity"] = statements["Equity"].replace("", np.nan).astype(float)                                      # 純資産
statements["BookValuePerShare"] = statements["BookValuePerShare"].replace("", np.nan).astype(float)                # 一株あたり純資産

statements["ROA"] = statements.apply(lambda row: round((row["OperatingProfit"] / row["TotalAssets"]) * 100, 2), axis=1)  # ROA (営業利益ベース)
statements["ROS"] = statements.apply(lambda row: round((row["OperatingProfit"] / row["NetSales"]) * 100, 2), axis=1)     # 売上高営業利益率ROS
statements["TOT"] = statements.apply(lambda row: round((row["NetSales"] / row["TotalAssets"]), 2), axis=1)               # 総資産回転率TOT
statements["ROE"] = statements.apply(lambda row: round((row["Profit"] / row["Equity"]) * 100, 2), axis=1)                # ROE (純利益ベース)
statements["FL"] = statements.apply(lambda row: round((row["TotalAssets"] / row["Equity"]), 2), axis=1)                  # 財務レバレッジ

# 財務情報を表示
st.write("""#### 財務数値""")
st.caption(f"ℹ **{statements['CurrentPeriodEndDate'].iloc[-1]} / {statements['TypeOfCurrentPeriod'].iloc[-1]}** 終了時点")
st.write("")

# 4つのメトリック部分
col1, col2, col3, col4 = st.columns(4)
with col1:
    # ROA (営業利益ベース) の昨対比
    YoY_ROA = round(statements["ROA"].iloc[-1] - statements["ROA"].iloc[-5], 2)
    st.metric(label="ROA (営業利益ベース)", value=f"{statements['ROA'].iloc[-1]} %", delta=f"{YoY_ROA} % / YoY")
with col2:
    # 売上高営業利益率の昨対比
    YoY_ROS = round(statements["ROS"].iloc[-1] - statements["ROS"].iloc[-5], 2)
    st.metric(label="売上高営業利益率", value=f"{statements['ROS'].iloc[-1]} %", delta=f"{YoY_ROS} % / YoY")
with col3:
    # 総資産回転率の昨対比
    YoY_TOT = round(statements["TOT"].iloc[-1] - statements["TOT"].iloc[-5], 2)
    st.metric(label="総資産回転率", value=f"{statements['TOT'].iloc[-1]} 回", delta=f"{YoY_TOT} 回 / YoY")
with col4:
    # ROE (純利益ベース) の昨対比
    YoY_ROE = round(statements["ROE"].iloc[-1] - statements["ROE"].iloc[-5], 2)
    st.metric(label="ROE (純利益ベース)", value=f"{statements['ROE'].iloc[-1]} %", delta=f"{YoY_ROE} % / YoY")

st.write("")

# ROAとROEの棒グラフ
col1, col2 = st.columns(2)
with col1:
    st.write("""###### ROAとROE""")
    
    plt.figure()
    plt.bar(statements["CurrentPeriodEndDate"], statements["ROA"], align="edge", width=-0.3, label="ROA")
    plt.bar(statements["CurrentPeriodEndDate"], statements["ROE"], align="edge", width= 0.3, label="ROE")
    plt.xticks(rotation='vertical')
    plt.ylabel("%")
    plt.legend()
    st.pyplot(plt)

# ROEのブレークダウンの棒グラフ
with col2:
    st.write("""###### ROEのブレークダウン""")
    
    fig, ax1 = plt.subplots(figsize=(6, 4.8))
    x = np.arange(len(statements["CurrentPeriodEndDate"]))
    labels = statements["CurrentPeriodEndDate"]
    bar_plot_statements = statements.rename(columns={"ROS": "売上高営業利益率", "TOT": "総資産回転率", "FL": "財務レバレッジ"})

    margin = 0.2
    total_width = 1 - margin

    # y軸の単位 (左)
    ax1.bar(x - total_width / 3, bar_plot_statements["売上高営業利益率"], width=total_width / 3, label="営業利益率", color="C0")
    ax1.set_ylim(0.0, 60.0)
    ax1.set_ylabel("%")
    plt.legend(loc="upper left")
    ax1.set_xticks(x, labels, rotation="vertical")

    # y軸の単位 (右)
    ax2 = ax1.twinx()
    ax2.bar(x, bar_plot_statements["総資産回転率"], width=total_width / 3, label="資産回転率", color="C1")
    ax2.bar(x + total_width / 3, bar_plot_statements["財務レバレッジ"], width=total_width / 3, label="財務レバレッジ", color="C2")
    ax2.set_ylim(0.0, 6.0)
    ax2.set_ylabel("%")
    ax2.legend(loc="upper right")

    st.pyplot(fig)

st.write("")
st.write("")

# 3つのメトリック部分
col1, col2, col3 = st.columns([1, 1, 1])
    
## PER (最新のEPS公表時点)
calc_PER = statements[["CurrentPeriodEndDate", "EarningsPerShare"]].merge(daily_quotes[["Date", "AdjustmentClose"]], how="left", left_on="CurrentPeriodEndDate", right_on="Date")
PER = round((calc_PER["AdjustmentClose"] / calc_PER["EarningsPerShare"]), 2).iloc[-1]

## 予想売上高営業利益率
per_change = statements["ROS"].iloc[-1] / statements["ROS"].iloc[-5]
forecast_ROS = round((statements["ROS"].iloc[-1] * per_change), 2)

## 予想売上高成長率
forecast_growth_rate = round((statements["NetSales"].iloc[-1] / statements["NetSales"].iloc[-5]), 2)

with col1:
    st.metric(label="PER", value=f"{PER} 倍")
with col2:
    st.metric(label="予想売上高営業利益率", value=f"{forecast_ROS} %")
with col3:
    st.metric(label="予想売上高成長率", value=f"{forecast_growth_rate} %")