import re

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# Add imports
imports = """import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';"""
content = content.replace('"use client";\n', '"use client";\n\n' + imports + '\n')

# Update rendering
old_render = """<p>{currentChapter.content}</p>"""
new_render = """<div className="prose prose-sm md:prose-base prose-slate max-w-none w-full">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {currentChapter.content}
                            </ReactMarkdown>
                          </div>"""
content = content.replace(old_render, new_render)

# Remove whitespace-pre-wrap from container to let ReactMarkdown handle formatting
container_old = """<div className="text-slate-600 leading-relaxed min-h-[200px] whitespace-pre-wrap">"""
container_new = """<div className="text-slate-600 leading-relaxed min-h-[200px]">"""
content = content.replace(container_old, container_new)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

print("Markdown patch applied.")
