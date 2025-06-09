import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

def record_to_sheet(data, config):
    """
    구글 스프레드시트에 매매 데이터를 기록합니다.
    """
    try:
        sheet_id = config.get("sheet_id")
        sheet_tab = config.get("sheet_tab", "자동기록")

        # 인증 파일 경로 (JSON 키파일 업로드 필요)
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "gspread_key.json",
            ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )

        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).worksheet(sheet_tab)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([
            now,
            data.get("종목"),
            data.get("전략"),
            data.get("진입가"),
            data.get("예상수익률"),
            data.get("진입시간")
        ])

    except Exception as e:
        print("시트 기록 오류:", e)
