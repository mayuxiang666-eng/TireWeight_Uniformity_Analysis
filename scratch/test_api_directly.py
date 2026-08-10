import sys
import os
sys.path.append(os.path.abspath('backend'))
from main import get_insights
import pprint

res = get_insights(
    baseline_from="2026-05-31",
    baseline_to="2026-06-02",
    study_from="2026-06-04",
    study_to="2026-06-06",
    min_yield=50,
    cv_threshold=0.4
)
pprint.pprint(res)
