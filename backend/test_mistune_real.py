import mistune
import json

md_parser = mistune.create_markdown(renderer='ast', plugins=['table'])
markdown_text = """
| 逻辑数据类型 | MySQL (关系型通用) | Greenplum (分布式数据仓库) | ClickHouse (列式分析引擎) |
| :--- | :--- | :--- | :--- |
| 字符串 (Short) | VARCHAR(255) | VARCHAR(255) | String 或 FixedString |
"""
ast = md_parser(markdown_text)
print(json.dumps(ast, indent=2))
