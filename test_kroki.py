import requests

url = "http://localhost:8000/mermaid/png"
headers = {
    "Content-Type": "text/plain",
    "User-Agent": "Mozilla/5.0"
}
mermaid_code = """flowchart TD
    A["项目人员供给保障领导小组"] --> B["人员供给保障工作办公室"]
    B --> C["招募配置组"]
    B --> D["培训考核组"]
    B --> E["动态调配组"]
    B --> F["薪酬绩效组"]
    B --> G["应急保障组"]
    A --> H["各专业施工队"]
    A --> I["劳务合作队"]
    A --> J["外部专家顾问"]
    H --> K["作业班组"]
    I --> L["劳务人员"]"""

try:
    print("Testing plain POST with mermaid code...")
    res = requests.post(url, data=mermaid_code.strip().encode('utf-8'), headers=headers)
    print(res.status_code)
    if res.status_code != 200:
        print(res.text)
    else:
        print(f"Success, length: {len(res.content)}")
except Exception as e:
    print(e)
