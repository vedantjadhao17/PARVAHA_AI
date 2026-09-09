import requests
import time
import sys

print("Polling for pending recommendations...")
rec_id = None

while True:
    try:
        res = requests.get("http://localhost:8000/api/corridor/state").json()
        time_s = res.get("time_s", 0)
        pending = res.get("pending_recommendations", [])
        print(f"Time: {time_s}s, Pending: {len(pending)}")
        
        if pending:
            rec_id = pending[0].get("recommendation_id")
            if rec_id:
                print(f"Found recommendation! ID: {rec_id}")
                break
                
        if time_s > 580:
            print("Failed to find recommendation before 450s!")
            sys.exit(1)
            
    except Exception as e:
        pass
    time.sleep(5)

print(f"Approving recommendation {rec_id}...")
app_res = requests.post(f"http://localhost:8000/api/recommendations/{rec_id}/approve")
print(f"Approve Response: {app_res.status_code} - {app_res.text}")
if app_res.status_code != 200:
    sys.exit(1)

time.sleep(2)

print(f"Rolling back recommendation {rec_id}...")
rb_res = requests.post(f"http://localhost:8000/api/recommendations/{rec_id}/rollback")
print(f"Rollback Response: {rb_res.status_code} - {rb_res.text}")
if rb_res.status_code != 200:
    sys.exit(1)
    
print("Success!")
sys.exit(0)
