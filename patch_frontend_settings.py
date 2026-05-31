import re

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# 1. Revert handleSelectChapter
old_select = """const handleSelectChapter = (chapterId: string) => {
    setActiveChapterId(chapterId);
    
    const chapterIndex = flatOutline.findIndex(c => c.id === chapterId);
    if (chapterIndex !== -1 && chapterIndex + 1 < flatOutline.length) {
      if (flatOutline[chapterIndex + 1].level > flatOutline[chapterIndex].level) {
        // If it's a non-leaf node, auto-submit its leaves
        enqueueGeneration(chapterId);
      }
    }
  };"""
new_select = """const handleSelectChapter = (chapterId: string) => {
    setActiveChapterId(chapterId);
  };"""
content = content.replace(old_select, new_select)

# 2. Add Settings state
state_old = "const [isTaskPanelOpen, setIsTaskPanelOpen] = useState(false);"
state_new = """const [isTaskPanelOpen, setIsTaskPanelOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState(`You are an expert Bid Architect (Commander) specializing in enterprise-grade proposals.
Your task is to rewrite, refine, or expand the Document Outline based on user instructions.

CRITICAL REQUIREMENTS:
1. Structure: Ensure a highly logical, MECE (Mutually Exclusive, Collectively Exhaustive) hierarchy.
2. Granularity: Break down complex sections into detailed sub-sections (Level 3 or 4) to provide clear guidance for the content writers.
3. Professionalism: Use formal, precise terminology suitable for government or enterprise bidding.
4. Formatting: 
   - Level 1: 第一章, 第二章...
   - Level 2: 1.1, 1.2...
   - Level 3: 1.1.1, 1.1.2...`);"""
content = content.replace(state_old, state_new)

# 3. Add Settings button onClick
settings_btn_old = """<Button variant="ghost" size="icon" className="text-slate-500 hover:text-slate-700">
            <Settings size={18} />
          </Button>"""
settings_btn_new = """<Button variant="ghost" size="icon" className="text-slate-500 hover:text-slate-700" onClick={() => setIsSettingsOpen(true)}>
            <Settings size={18} />
          </Button>"""
content = content.replace(settings_btn_old, settings_btn_new)

# 4. Add system_prompt to payload
payload_old = """body: JSON.stringify({
              instruction: userMsg,
              current_outline: flatOutline,
              active_chapter_id: activeChapterId
            })"""
payload_new = """body: JSON.stringify({
              instruction: userMsg,
              current_outline: flatOutline,
              active_chapter_id: activeChapterId,
              system_prompt: systemPrompt
            })"""
content = content.replace(payload_old, payload_new)

# 5. Add Modal HTML before closing div
modal_html = """
      {/* Settings Modal */}
      {isSettingsOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200 border border-slate-200">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2"><Settings size={18} className="text-primary"/> 提示词与系统配置 (Settings)</h2>
              <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-slate-700" onClick={() => setIsSettingsOpen(false)}>
                <X size={18} />
              </Button>
            </div>
            <div className="p-6 flex-1">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-1">目录大纲重构系统提示词 (Outline Commander Prompt)</label>
                  <p className="text-xs text-slate-500 mb-3">此提示词将被注入到 Gemini API 中，专门用于控制“一键重构目录”时的架构、专业度和拆解颗粒度。</p>
                  <textarea 
                    className="w-full h-72 p-4 rounded-lg border border-slate-200 focus:border-primary focus:ring-1 focus:ring-primary outline-none resize-none font-mono text-sm bg-slate-50/50 text-slate-700 leading-relaxed shadow-inner"
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                  />
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t bg-slate-50 flex justify-end gap-3">
              <Button variant="outline" onClick={() => setIsSettingsOpen(false)}>取消</Button>
              <Button onClick={() => setIsSettingsOpen(false)}>保存配置</Button>
            </div>
          </div>
        </div>
      )}
"""
content = content.replace("    </div>\n  );\n}", modal_html + "    </div>\n  );\n}")

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

print("Frontend patched for settings.")
