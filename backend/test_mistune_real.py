import mistune
import json

md_parser = mistune.create_markdown(renderer='ast', plugins=['table'])
markdown_text = """
| Header 1 | Header 2 |
|---|---|
| Row 1 | Row 2 |
"""
ast = md_parser(markdown_text)
print(json.dumps(ast, indent=2))
