from config import *
from angel_login import connect
print("======================================")
print(APP_NAME)
print("Version:", VERSION)
print("======================================")
print("Exchange :", EXCHANGE)
print("Timeframe:", TIMEFRAME)
print("Loading modules...")
connect()
print("Ready to start scanner...")