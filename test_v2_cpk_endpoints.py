import urllib.request
import urllib.parse
import json

def test_endpoint(url):
    print(f"Testing URL: {url}")
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
        print("  Status:", data.get("status"))
        if data.get("status") == "success":
            d = data.get("data", {})
            print("  Keys/Items count:", len(d))
            if isinstance(d, dict):
                for k in list(d.keys())[:3]:
                    print(f"    Sample key '{k}': {len(d[k])} items")
            elif isinstance(d, list):
                print(f"    Sample items: {d[:3]}")
        else:
            print("  Error message:", data.get("message"))
    except Exception as e:
        print("  Failed:", e)

# Find first date with warnings
try:
    response = urllib.request.urlopen('http://127.0.0.1:8000/api/trend/cpk?grain=daily')
    trend_data = json.loads(response.read())
    dates = trend_data.get("data", {}).get("dates", [])
    
    found_date = None
    found_article = None
    
    for d in dates:
        warn_url = f'http://127.0.0.1:8000/api/articles/warning-cpk?study_from={d}&study_to={d}&indicator=rfh1'
        warn_res = urllib.request.urlopen(warn_url)
        warn_data = json.loads(warn_res.read())
        articles = warn_data.get("data", [])
        if articles:
            found_date = d
            found_article = articles[0].get("article10")
            break
            
    if found_date and found_article:
        print(f"Found test date: {found_date}, article: {found_article}")
        
        # Test /api/machines/cpk
        machines_url = f"http://127.0.0.1:8000/api/machines/cpk?target_date={found_date}&article10={found_article}&indicator=rfh1&min_samples=2"
        test_endpoint(machines_url)
        
        # Now test /api/machines/cpk/trend
        mach_res = urllib.request.urlopen(machines_url)
        mach_data = json.loads(mach_res.read())
        mach_groups = mach_data.get("data", {})
        if mach_groups:
            first_group = list(mach_groups.keys())[0]
            first_machine_item = mach_groups[first_group][0]
            machine = first_machine_item.get("machine")
            wc_col = first_machine_item.get("workcenter_col")
            print(f"Found active machine: {machine}, workcenter: {wc_col}")
            
            # Print if warning flag is set
            print(f"  spec_declining_warning: {first_machine_item.get('spec_declining_warning')}")
            print(f"  all_declining_warning: {first_machine_item.get('all_declining_warning')}")
            
            trend_url = f"http://127.0.0.1:8000/api/machines/cpk/trend?machine={urllib.parse.quote(machine)}&workcenter_col={urllib.parse.quote(wc_col)}&indicator=rfh1&article10={found_article}"
            test_endpoint(trend_url)
    else:
        print("No date with warnings found.")
except Exception as e:
    print("Verification request failed:", e)
