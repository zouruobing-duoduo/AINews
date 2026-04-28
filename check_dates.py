"""检查日期"""
from datetime import datetime, timedelta

# 获取今天日期
today = datetime.now()
print(f'今天: {today.strftime("%Y-%m-%d")} (weekday={today.weekday()})')

# 计算上周六和周日
# weekday(): Monday=0, Sunday=6
# 上周六 = 今天 - (今天星期几 + 2)天
# 上周日 = 今天 - (今天星期几 + 1)天
days_to_last_sat = today.weekday() + 2  # 到上周六的天数
days_to_last_sun = today.weekday() + 1  # 到上周日的天数

last_saturday = today - timedelta(days=days_to_last_sat)
last_sunday = today - timedelta(days=days_to_last_sun)

print(f'上周六: {last_saturday.strftime("%Y-%m-%d")}')
print(f'上周日: {last_sunday.strftime("%Y-%m-%d")}')
