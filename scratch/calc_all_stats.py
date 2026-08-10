import urllib.request
import json
import numpy as np

url = 'http://127.0.0.1:8000/api/trend/cpk?grain=daily&article10=0359791000'
try:
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    rfh1 = [v for v in data["data"]["cpk_trends"]["RFH1 综合 CPK"] if v is not None]
    
    print(f"Total points: {len(rfh1)}")
    print(f"Mean of all 26 points: {np.mean(rfh1):.4f}")
    print(f"Std of all 26 points: {np.std(rfh1, ddof=1):.4f}")
    print(f"Mean - Std: {np.mean(rfh1) - np.std(rfh1, ddof=1):.4f}")
except Exception as e:
    print("Error:", e)
