import re
import sys

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# 1. Add imports
content = content.replace(
    "Loader2\n} from \"lucide-react\";",
    "Loader2,\n  Play, Pause, XCircle, RefreshCw, X, AlertCircle\n} from \"lucide-react\";"
)

# 2. Add GenTask type
content = content.replace(
    "interface Message {",
    "export interface GenTask {\n  chapterId: string;\n  status: \"queued\" | \"generating\" | \"success\" | \"error\";\n  error?: string;\n  abortController?: AbortController;\n}\n\ninterface Message {"
)

# 3. Update TreeItem signature and rendering
tree_item_old = """const TreeItem = ({ 
  item, 
  activeId, 
  onSelect, 
  expandedIds, 
  toggleExpand 
}: { 
  item: OutlineItem; 
  activeId: string; 
  onSelect: (id: string) => void;
  expandedIds: Set<string>;
  toggleExpand: (id: string) => void;
}) => {"""

tree_item_new = """const TreeItem = ({ 
  item, 
  activeId, 
  onSelect, 
  expandedIds, 
  toggleExpand,
  taskQueue
}: { 
  item: OutlineItem; 
  activeId: string; 
  onSelect: (id: string) => void;
  expandedIds: Set<string>;
  toggleExpand: (id: string) => void;
  taskQueue: Record<string, GenTask>;
}) => {
  const task = taskQueue[item.id];"""

content = content.replace(tree_item_old, tree_item_new)

# Update TreeItem status icon
status_old = "{item.status === 'completed' && <CheckCircle2 size={12} className=\"text-emerald-500 shrink-0\" />}"
status_new = """{task?.status === 'generating' && <Loader2 size={12} className="text-primary animate-spin shrink-0" />}
        {task?.status === 'queued' && <RefreshCw size={12} className="text-slate-400 shrink-0" />}
        {task?.status === 'error' && <AlertCircle size={12} className="text-red-500 shrink-0" />}
        {(item.status === 'completed' || task?.status === 'success') && <CheckCircle2 size={12} className="text-emerald-500 shrink-0" />}"""
content = content.replace(status_old, status_new)

# Update TreeItem recursion
recursion_old = """<TreeItem 
              key={child.id} 
              item={child} 
              activeId={activeId} 
              onSelect={onSelect} 
              expandedIds={expandedIds} 
              toggleExpand={toggleExpand} 
            />"""
recursion_new = """<TreeItem 
              key={child.id} 
              item={child} 
              activeId={activeId} 
              onSelect={onSelect} 
              expandedIds={expandedIds} 
              toggleExpand={toggleExpand} 
              taskQueue={taskQueue}
            />"""
content = content.replace(recursion_old, recursion_new)

# 4. State updates in Dashboard
state_old = """const [activeChapterId, setActiveChapterId] = useState<string>("2.1");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set(["2"]));
  const [generatingIds, setGeneratingIds] = useState<Set<string>>(new Set());"""

state_new = """const [activeChapterId, setActiveChapterId] = useState<string>("2.1");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set(["2"]));
  const [taskQueue, setTaskQueue] = useState<Record<string, GenTask>>({});
  const [isTaskPanelOpen, setIsTaskPanelOpen] = useState(false);
  const MAX_CONCURRENT_TASKS = 3;"""

content = content.replace(state_old, state_new)

# 5. Add Queue Logic and getLeafNodes
hook_inject_target = "const treeOutline = useMemo(() => buildTree(flatOutline), [flatOutline]);"
hook_inject_new = """const treeOutline = useMemo(() => buildTree(flatOutline), [flatOutline]);

  const getLeafNodes = (outline: OutlineItem[], rootId: string): OutlineItem[] => {
    const rootIndex = outline.findIndex(item => item.id === rootId);
    if (rootIndex === -1) return [];
    const rootItem = outline[rootIndex];
    const descendants: OutlineItem[] = [];
    for (let i = rootIndex + 1; i < outline.length; i++) {
      if (outline[i].level <= rootItem.level) break;
      descendants.push(outline[i]);
    }
    if (descendants.length === 0) return [rootItem];
    const leaves: OutlineItem[] = [];
    for (let i = 0; i < descendants.length; i++) {
      const current = descendants[i];
      const next = descendants[i + 1];
      if (!next || next.level <= current.level) {
        leaves.push(current);
      }
    }
    return leaves;
  };

  const enqueueGeneration = (chapterId: string) => {
    const leaves = getLeafNodes(flatOutline, chapterId);
    setTaskQueue(prev => {
      const newQueue = { ...prev };
      leaves.forEach(leaf => {
        if (!newQueue[leaf.id] || newQueue[leaf.id].status === 'error') {
          newQueue[leaf.id] = { chapterId: leaf.id, status: 'queued' };
        }
      });
      return newQueue;
    });
    setMessages(prev => [...prev, {
      role: "assistant",
      content: `⏳ 已将《${flatOutline.find(c => c.id === chapterId)?.title}》及其子章节共 ${leaves.length} 个任务加入生成队列。`
    }]);
    setIsTaskPanelOpen(true);
  };

  const cancelTask = (chapterId: string) => {
    setTaskQueue(prev => {
      const newQ = { ...prev };
      const task = newQ[chapterId];
      if (task?.abortController) {
        task.abortController.abort();
      }
      delete newQ[chapterId];
      return newQ;
    });
  };

  useEffect(() => {
    const processQueue = async () => {
      const tasks = Object.values(taskQueue);
      const generatingCount = tasks.filter(t => t.status === 'generating').length;
      if (generatingCount >= MAX_CONCURRENT_TASKS) return;
      
      const queuedTask = tasks.find(t => t.status === 'queued');
      if (!queuedTask) return;
      
      const controller = new AbortController();
      setTaskQueue(prev => ({
        ...prev,
        [queuedTask.chapterId]: { ...prev[queuedTask.chapterId], status: 'generating', abortController: controller }
      }));
      
      const chapter = flatOutline.find(c => c.id === queuedTask.chapterId);
      if (!chapter) {
        setTaskQueue(prev => ({ ...prev, [queuedTask.chapterId]: { ...prev[queuedTask.chapterId], status: 'error', error: 'Chapter not found' } }));
        return;
      }
      
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(`${apiUrl}/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            sections: [{ id: chapter.id, title: chapter.title, level: chapter.level, index: parseInt(chapter.id.split('.').pop() || '0') || 0, context: "" }],
            global_guidelines: ""
          }),
        });

        if (!response.ok) throw new Error("生成请求失败");
        const data = await response.json();
        
        if (data.results && data.results.length > 0 && data.results[0].status === "success") {
          const generatedContent = data.results[0].data;
          setFlatOutline(prev => prev.map(item => item.id === chapter.id ? { ...item, content: generatedContent, status: "completed" } : item));
          setTaskQueue(prev => ({ ...prev, [chapter.id]: { ...prev[chapter.id], status: "success" } }));
        } else {
          throw new Error(data.results?.[0]?.error || "生成失败");
        }
      } catch (error: any) {
        if (error.name !== "AbortError") {
           setTaskQueue(prev => ({ ...prev, [chapter.id]: { ...prev[chapter.id], status: "error", error: error.message } }));
        }
      }
    };
    processQueue();
  }, [taskQueue, flatOutline]);"""

content = content.replace(hook_inject_target, hook_inject_new)

# 6. Remove handleGenerate old function
content = re.sub(r'const handleGenerate = async \(chapterId: string\) => \{[\s\S]*?\}\;\n\n  const handleExportOutline', 'const handleExportOutline', content)

# 7. Update Tree rendering calls in JSX
tree_render_old = """<TreeItem 
                key={item.id} 
                item={item} 
                activeId={activeChapterId} 
                onSelect={setActiveChapterId} 
                expandedIds={expandedIds}
                toggleExpand={toggleExpand}
              />"""
tree_render_new = """<TreeItem 
                key={item.id} 
                item={item} 
                activeId={activeChapterId} 
                onSelect={setActiveChapterId} 
                expandedIds={expandedIds}
                toggleExpand={toggleExpand}
                taskQueue={taskQueue}
              />"""
content = content.replace(tree_render_old, tree_render_new)

# 8. Update generatingIds logic in UI
content = content.replace("generatingIds.has(activeChapterId)", "(taskQueue[activeChapterId]?.status === 'generating' || taskQueue[activeChapterId]?.status === 'queued')")
content = content.replace("onClick={() => handleGenerate(activeChapterId)}", "onClick={() => enqueueGeneration(activeChapterId)}")

# 9. Add Task Panel UI
# Find the end of <main> to inject task panel
main_end = "</main>"
task_panel = """
      {/* 任务监控悬浮窗 */}
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
      )}
</main>
"""
content = content.replace(main_end, task_panel)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

print("Patch applied.")
