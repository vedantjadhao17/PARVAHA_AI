import requests
import time

while True:
    try:
        res = requests.get("http://localhost:8000/api/alerts").json()
        for alert in res:
            if alert.get("recommendation_id") and not alert.get("is_sample"):
                print(f"Recommendation appeared! ID: {alert['recommendation_id']}")
                print(f"Time: {requests.get('http://localhost:8000/api/corridor/state').json()['time_s']}")
                exit(0)
    except:
        pass
    time.sleep(5)
