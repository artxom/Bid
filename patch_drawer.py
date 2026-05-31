import sys

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

old_panel = """{/* 任务监控悬浮窗 */}
      {isTaskPanelOpen && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 w-96 bg-white rounded-xl shadow-2xl border border-slate-200 z-50 overflow-hidden flex flex-col max-h-[400px]">
          <div className="bg-slate-800 text-white px-4 py-3 flex items-center justify-between shrink-0">
            <h3 className="font-semibold text-sm flex items-center gap-2">
              <RefreshCw size={14} className="animate-spin-slow" />
              生成任务监控
            </h3>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-slate-300 hover:text-white hover:bg-slate-700 rounded-full" onClick={() => setIsTaskPanelOpen(false)}>
              <X size={14} />
            </Button>
          </div>
          <ScrollArea className="flex-1 p-0">
            {Object.values(taskQueue).length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-sm">暂无生成任务</div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {Object.values(taskQueue).map(task => {
                  const chapter = flatOutline.find(c => c.id === task.chapterId);
                  return (
                    <li key={task.chapterId} className="px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors group">
                      <div className="flex items-center gap-3 overflow-hidden">
                        {task.status === 'generating' && <Loader2 size={14} className="text-primary animate-spin shrink-0" />}
                        {task.status === 'queued' && <RefreshCw size={14} className="text-slate-400 shrink-0" />}
                        {task.status === 'success' && <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />}
                        {task.status === 'error' && <AlertCircle size={14} className="text-red-500 shrink-0" />}
                        <span className="text-sm font-medium text-slate-700 truncate">{chapter?.title || task.chapterId}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {task.status === 'error' && (
                          <Button variant="ghost" size="icon" className="h-6 w-6 text-slate-400 hover:text-primary" onClick={() => enqueueGeneration(task.chapterId)}>
                            <RefreshCw size={12} />
                          </Button>
                        )}
                        {(task.status === 'generating' || task.status === 'queued') && (
                          <Button variant="ghost" size="icon" className="h-6 w-6 text-slate-400 hover:text-red-500" onClick={() => cancelTask(task.chapterId)}>
                            <XCircle size={12} />
                          </Button>
                        )}
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </ScrollArea>
        </div>
      )}"""

new_panel = """{/* 任务监控悬浮窗与按钮 (Bottom Right Drawer) */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
        {isTaskPanelOpen && (
          <div className="w-80 bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col h-[400px] animate-in slide-in-from-bottom-5">
            <div className="bg-slate-800 text-white px-4 py-3 flex items-center justify-between shrink-0 shadow-sm">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <RefreshCw size={14} className={Object.values(taskQueue).some(t => t.status === 'generating') ? "animate-spin-slow" : ""} />
                并发任务队列 ({Object.values(taskQueue).filter(t => t.status === 'generating').length}/{MAX_CONCURRENT_TASKS})
              </h3>
              <Button variant="ghost" size="icon" className="h-6 w-6 text-slate-300 hover:text-white hover:bg-slate-700 rounded-full" onClick={() => setIsTaskPanelOpen(false)}>
                <X size={14} />
              </Button>
            </div>
            <ScrollArea className="flex-1 p-0 bg-slate-50">
              {Object.values(taskQueue).length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full p-6 text-slate-400 text-sm gap-2">
                  <CheckCircle2 size={32} className="text-slate-300 opacity-50" />
                  <span>暂无运行中的生成任务</span>
                </div>
              ) : (
                <ul className="divide-y divide-slate-100 bg-white">
                  {Object.values(taskQueue).map(task => {
                    const chapter = flatOutline.find(c => c.id === task.chapterId);
                    return (
                      <li key={task.chapterId} className="px-4 py-3 flex items-center justify-between hover:bg-slate-50/80 transition-colors group">
                        <div className="flex items-center gap-3 overflow-hidden flex-1 mr-2">
                          <div className="shrink-0">
                            {task.status === 'generating' && <Loader2 size={16} className="text-blue-500 animate-spin" />}
                            {task.status === 'queued' && <RefreshCw size={16} className="text-slate-300" />}
                            {task.status === 'success' && <CheckCircle2 size={16} className="text-emerald-500" />}
                            {task.status === 'error' && <AlertCircle size={16} className="text-rose-500" />}
                          </div>
                          <span className="text-[13px] font-medium text-slate-700 truncate" title={chapter?.title || task.chapterId}>
                            {chapter?.title || task.chapterId}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                          {task.status === 'error' && (
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-400 hover:text-blue-600 hover:bg-blue-50" onClick={() => enqueueGeneration(task.chapterId)} title="重试">
                              <RefreshCw size={14} />
                            </Button>
                          )}
                          {(task.status === 'generating' || task.status === 'queued') && (
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-400 hover:text-rose-600 hover:bg-rose-50" onClick={() => cancelTask(task.chapterId)} title="取消">
                              <XCircle size={14} />
                            </Button>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </ScrollArea>
          </div>
        )}
        
        {!isTaskPanelOpen && (
          <Button 
            className="h-12 w-12 rounded-full shadow-xl bg-slate-800 hover:bg-slate-700 text-white border border-slate-600 relative overflow-hidden" 
            onClick={() => setIsTaskPanelOpen(true)}
          >
            <RefreshCw size={20} className={Object.values(taskQueue).some(t => t.status === 'generating') ? "animate-spin-slow" : ""} />
            {Object.values(taskQueue).length > 0 && (
              <span className="absolute top-0 right-0 h-3.5 w-3.5 bg-rose-500 rounded-full flex items-center justify-center text-[9px] font-bold border-2 border-slate-800">
                {Object.values(taskQueue).length}
              </span>
            )}
          </Button>
        )}
      </div>"""

content = content.replace(old_panel, new_panel)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

print("Drawer patched.")
