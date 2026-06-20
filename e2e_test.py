"""BASS-MVP 端到端主流程验证脚本"""
import requests
import os
import json
import time

BASE_URL = "http://localhost:8006/api/v1"
base_dir = os.path.dirname(os.path.abspath(__file__))

PID = "66554705-cde6-4e95-a27e-4005c7b716f3"

# ===== 步骤 3 (已完成上传, 现在提取 DOC_ID)
print("=" * 60)
print("步骤 3: 上传文件")
print("=" * 60)
url = f"{BASE_URL}/projects/{PID}/documents/upload"
file_path = os.path.join(base_dir, 'e2e_bid.pdf')
with open(file_path, 'rb') as f:
    resp = requests.post(url, files={'file': ('e2e_bid.pdf', f, 'application/pdf')})
print(f"Status: {resp.status_code}")
data = resp.json()
print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
DOC_ID = data.get('data', {}).get('id', '')
print(f"DOC_ID={DOC_ID}")
assert resp.status_code == 200
assert data.get('code') == 0
assert data.get('data', {}).get('filename') == 'e2e_bid.pdf'
assert data.get('data', {}).get('status') == 'uploaded'
print(">>> PASS")

# ===== 步骤 4: 触发文档解析
print()
print("=" * 60)
print("步骤 4: 触发文档解析")
print("=" * 60)
url = f"{BASE_URL}/projects/{PID}/documents/{DOC_ID}/parse"
resp = requests.post(url)
print(f"Status: {resp.status_code}")
data = resp.json()
print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
assert resp.status_code == 200
print(">>> PASS (触发解析)")

# 等待解析完成
print("等待解析...")
for i in range(6):
    time.sleep(5)
    url = f"{BASE_URL}/projects/{PID}/documents/{DOC_ID}/parse-status"
    resp = requests.get(url)
    try:
        data = resp.json()
        ps = data.get('data', {}).get('parse_status', '')
        print(f"  [第{(i+1)*5}s] parse_status={ps}")
        if ps == 'completed':
            print(">>> 解析完成!")
            break
    except:
        print(f"  [第{(i+1)*5}s] 响应: {resp.text}")
else:
    print(">>> 警告: 解析未在30秒内完成")

# ===== 步骤 5: 启动分析任务
print()
print("=" * 60)
print("步骤 5: 启动分析任务")
print("=" * 60)
url = f"{BASE_URL}/analysis/tasks"
resp = requests.post(url, json={"project_id": PID, "task_type": "full_analysis"})
print(f"Status: {resp.status_code}")
data = resp.json()
print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
TID = data.get('data', {}).get('id', '')
print(f"TID={TID}")
assert resp.status_code == 200
assert data.get('code') == 0
assert TID != ''
print(">>> PASS (分析任务创建)")

# 等待分析完成
print("等待分析完成...")
for i in range(12):
    time.sleep(10)
    url = f"{BASE_URL}/analysis/tasks/{TID}"
    resp = requests.get(url)
    try:
        data = resp.json()
        status = data.get('data', {}).get('status', '')
        progress = data.get('data', {}).get('progress', '')
        print(f"  [第{(i+1)*10}s] status={status}, progress={progress}")
        if status in ('completed', 'success'):
            print(">>> 分析完成!")
            break
        if status == 'failed':
            print(f">>> 分析失败! error: {data.get('data', {}).get('error', '')}")
            break
    except Exception as e:
        print(f"  [第{(i+1)*10}s] 错误: {e}")
        print(f"  响应: {resp.text[:200]}")
else:
    print(">>> 警告: 分析未在120秒内完成")

# ===== 步骤 6: 获取分析结果
print()
print("=" * 60)
print("步骤 6: 获取分析结果")
print("=" * 60)

# Similarity
url = f"{BASE_URL}/analysis/tasks/{TID}/similarity"
resp = requests.get(url)
print(f"相似度: Status={resp.status_code}, Response={resp.text[:300]}")

# Errors
url = f"{BASE_URL}/analysis/tasks/{TID}/errors"
resp = requests.get(url)
print(f"错误: Status={resp.status_code}, Response={resp.text[:300]}")

# Images
url = f"{BASE_URL}/analysis/tasks/{TID}/images"
resp = requests.get(url)
print(f"图片: Status={resp.status_code}, Response={resp.text[:300]}")

# ===== 步骤 7: 获取报告数据
print()
print("=" * 60)
print("步骤 7: 获取报告数据")
print("=" * 60)
url = f"{BASE_URL}/projects/{PID}/reports/data?task_id={TID}"
resp = requests.get(url)
print(f"Status: {resp.status_code}")
try:
    data = resp.json()
    print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
except:
    print(f"Response: {resp.text[:500]}")
print(f"Code={data.get('code')}")

# ===== 汇总
print()
print("=" * 60)
print("端到端测试完成!")
print("=" * 60)
