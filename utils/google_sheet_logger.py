import os
import gspread
import pandas as pd
import gspread_dataframe as gd

from google.oauth2.service_account import Credentials
from datetime import datetime

def log_trade_to_sheet(data):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("google_credentials.json", scopes=scope)
        gc = gspread.authorize(creds)

        sheet_name = "TradingBot_Report"
        sh = gc.open(sheet_name)
        worksheet = sh.worksheet("Raw_Data")

        # 데이터 정리 및 추가
        row = [
            data.get("date", datetime.now().strftime("%Y-%m-%d")),
            data.get("time", datetime.now().strftime("%H:%M:%S")),
            data.get("symbol", ""),
            data.get("type", ""),
            data.get("strategy", ""),
            data.get("buy_amount", ""),
            data.get("sell_amount", ""),
            data.get("profit_rate", ""),
            data.get("profit_amount", ""),
            data.get("balance", "")
        ]

        worksheet.append_row(row, value_input_option="USER_ENTERED")
        print(f"✅ 구글 시트 기록 완료: {row}")

    except Exception as e:
        print(f"❌ 구글 시트 기록 실패: {e}")

def update_summary_sheets():
    try:
        gc = gspread.service_account(filename='google_credentials.json')
        sh = gc.open("TradingBot_Report")
        raw_ws = sh.worksheet("Raw_Data")

        # Raw_Data 불러오기
        data = raw_ws.get_all_records()
        if not data:
            print("⚠️ Raw_Data 데이터 없음")
            return

        df = pd.DataFrame(data)
        df['날짜'] = pd.to_datetime(df['날짜'])

        summaries = {
            "Daily_Summary": df.groupby(df['날짜'].dt.date).agg({
                '매수금액': 'sum',
                '매도금액': 'sum',
                '수익금액': 'sum',
                '수익률(%)': 'mean'
            }).reset_index(),

            "Weekly_Summary": df.groupby(df['날짜'].dt.to_period('W').apply(lambda r: r.start_time.date())).agg({
                '매수금액': 'sum',
                '매도금액': 'sum',
                '수익금액': 'sum',
                '수익률(%)': 'mean'
            }).reset_index(),

            "Monthly_Summary": df.groupby(df['날짜'].dt.to_period('M').apply(lambda r: r.start_time.date())).agg({
                '매수금액': 'sum',
                '매도금액': 'sum',
                '수익금액': 'sum',
                '수익률(%)': 'mean'
            }).reset_index(),

            "Yearly_Summary": df.groupby(df['날짜'].dt.to_period('Y').apply(lambda r: r.start_time.date())).agg({
                '매수금액': 'sum',
                '매도금액': 'sum',
                '수익금액': 'sum',
                '수익률(%)': 'mean'
            }).reset_index(),
        }

        for sheet_name, summary_df in summaries.items():
            summary_df.rename(columns={'날짜': '기간'}, inplace=True)
            ws = sh.worksheet(sheet_name)
            ws.clear()
            gd.set_with_dataframe(ws, summary_df)
            print(f"✅ {sheet_name} 업데이트 완료")

    except Exception as e:
        print(f"❌ 요약 시트 업데이트 실패: {e}")
