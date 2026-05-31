with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

modal_html = """      {/* Settings Modal */}
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
# Replace the FIRST occurrence of the modal_html with an empty string
# The first occurrence is inside TreeItem
content = content.replace(modal_html, "", 1)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

print("Modal duplication fixed.")
