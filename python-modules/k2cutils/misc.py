from datetime import datetime
from pytz import timezone


def timestamp_to_utc_isoformat(ts):
    return datetime.utcfromtimestamp(int(ts)).isoformat()+'Z'


def timestamp_to_local_isoformat(ts):
    dt = datetime.fromtimestamp(int(ts))
    return dt.isoformat()

if __name__ == '__main__':
    ts = 1478849405
    print timestamp_to_utc_isoformat(ts)
    print timestamp_to_local_isoformat(ts)
