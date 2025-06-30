import pandas as pd
import gspread
import gspread_dataframe as gd
from utils.telegram import send_telegram


def evaluate_strategy_performance():
    try:
        gc = gspread.service_account(filename='google_credentials.json')
        sh = gc.open("TradingBot_Report")
        ws = sh.worksheet("Raw_Data")
        data = ws.get_all_records()

        if not data:
            print("⚠️ 평가용 데이터가 없습니다.")
            return

        df = pd.DataFrame(data)
        df['날짜'] = pd.to_datetime(df['날짜'])

        # 전략별, 구분별 그룹화
        summary = df.groupby(['전략', '구분']).agg({
            '수익금액': ['sum', 'mean'],
            '수익률(%)': ['mean'],
            '매수금액': 'sum',
            '매도금액': 'sum'
        }).reset_index()

        summary.columns = ['전략', '구분', '수익금합계', '평균수익금', '평균수익률', '총매수', '총매도']
        print(summary)

    except Exception as e:
        print(f"❌ 전략 평가 실패: {e}")


def send_monthly_report(config):
    import gspread
    import pandas as pd

    try:
        gc = gspread.service_account(filename='google_credentials.json')
        sh = gc.open("TradingBot_Report")
        sheet = sh.worksheet("Monthly_Summary")

        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        if df.empty:
            send_telegram("📊 월간 보고서: 데이터 없음", config)
            return

        latest_month = df['날짜'].max()[:7]
        df_month = df[df['날짜'].str.startswith(latest_month)]

        if df_month.empty:
            send_telegram(f"📊 {latest_month} 월간 보고서: 거래 데이터 없음", config)
            return

        total_trades = df_month['거래횟수'].sum()
        total_profit = df_month['수익금'].sum()
        avg_profit_rate = df_month['수익률'].mean()

        message = (
            f"📊 {latest_month} 월간 전략별 보고서\n"
            f"• 거래 횟수: {total_trades}회\n"
            f"• 총 수익금: {int(total_profit):,}원\n"
            f"• 평균 수익률: {avg_profit_rate:.2f}%"
        )
        send_telegram(message, config)
        print(message)

    except Exception as e:
        send_telegram(f"❌ 월간 보고서 전송 실패: {e}", config)
        print(f"❌ 월간 보고서 전송 실패: {e}")
