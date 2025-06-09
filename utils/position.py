def assign_position_size(score, total_capital=1000000):
    """
    스코어 점수에 따라 진입 비중 계산
    - 90점 이상: 100%
    - 80~89점: 70%
    - 70~79점: 30%
    - 70점 미만: 진입 불가
    """
    if score >= 90:
        return total_capital * 1.0
    elif score >= 80:
        return total_capital * 0.7
    elif score >= 70:
        return total_capital * 0.3
    else:
        return 0
