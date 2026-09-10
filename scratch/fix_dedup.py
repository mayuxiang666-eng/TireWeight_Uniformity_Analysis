with open('backend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('Total lines before:', len(lines))
# Find start of @app.get("/api/cgrs/controlled-analysis") after line 800
idx_start = -1
for i in range(800, len(lines)):
    if lines[i].startswith('@app.get("/api/cgrs/controlled-analysis")'):
        idx_start = i
        break

idx_end = -1
for i in range(idx_start + 1, len(lines)):
    if lines[i].startswith('def get_phase_sql_condition('):
        idx_end = i
        break

print('Replacing from line', idx_start + 1, 'to line', idx_end)

new_func = '''@app.get("/api/cgrs/controlled-analysis")
def get_cgrs_controlled_analysis(
    workcenter: str = Query(..., description="成型机台编号，如 TB122 或 TB243"),
    date: str = Query(..., description="查询日期，格式 YYYY-MM-DD"),
    article: Optional[str] = Query(None, description="规格代码 article10 (可选)"),
    indicator: Optional[str] = Query("rfpp", description="指标类型，如 rfpp, rfh1, cony, weight"),
    top_machines: Optional[str] = Query(None, description="前端传入的全局影响度<0的Top 3嫌疑机台列表，逗号分隔，如 TU6,CU718,TU3"),
    same_day_only: bool = Query(False, description="是否仅看调参当天样本，False为允许跨天取样")
):
    try:
        return compute_cgrs_controlled_analysis_data(
            workcenter=workcenter,
            date=date,
            article=article,
            indicator=indicator,
            top_machines=top_machines,
            same_day_only=same_day_only,
            limit_per_path=30
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"执行 CGRS 控制变量分析失败: {str(e)}",
            "has_cgrs": False,
            "conclusion_type": "error",
            "conclusion_title": "分析出错",
            "conclusion_text": f"分析出错: {str(e)}",
            "events": []
        }


'''

new_lines = lines[:idx_start] + [new_func] + lines[idx_end:]
with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Total lines after:', len(new_lines))
