"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { 
  FileText, 
  Upload, 
  MessageSquare, 
  ChevronDown, 
  ChevronRight,
  Settings, 
  Plus, 
  Search,
  Send,
  CheckCircle2,
  Loader2,
  Play, Pause, XCircle, RefreshCw, X, AlertCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface OutlineItem {
  id: string;
  title: string;
  level: number;
  status?: "completed" | "in-progress" | "todo";
  children?: OutlineItem[];
  content?: string;
}

export interface GenTask {
  chapterId: string;
  status: "queued" | "generating" | "success" | "error";
  error?: string;
  abortController?: AbortController;
}

interface Message {
  role: "assistant" | "user";
  content: string;
}

// Helper to build tree from flat list
const buildTree = (items: OutlineItem[]): OutlineItem[] => {
  const root: OutlineItem[] = [];
  const stack: OutlineItem[] = [];

  items.forEach(item => {
    const node: OutlineItem = { ...item, children: [] };
    
    while (stack.length > 0 && stack[stack.length - 1].level >= node.level) {
      stack.pop();
    }

    if (stack.length === 0) {
      root.push(node);
    } else {
      stack[stack.length - 1].children!.push(node);
    }
    
    stack.push(node);
  });

  return root;
};

// Recursive Tree Component
const TreeItem = ({ 
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
  const task = taskQueue[item.id];
  const hasChildren = item.children && item.children.length > 0;
  const isExpanded = expandedIds.has(item.id);
  const isActive = activeId === item.id;

  return (
    <div className="space-y-0.5">
      <div 
        className={`flex items-center group cursor-pointer rounded-md transition-all h-9 px-2 gap-1 ${
          isActive ? 'bg-primary/10 text-primary' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
        }`}
        onClick={() => onSelect(item.id)}
      >
        <div 
          className="w-5 h-5 flex items-center justify-center rounded-sm hover:bg-slate-200 transition-colors"
          onClick={(e) => {
            if (hasChildren) {
              e.stopPropagation();
              toggleExpand(item.id);
            }
          }}
        >
          {hasChildren ? (
            isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : null}
        </div>
        <span className={`truncate flex-1 text-sm font-medium ${item.level === 1 ? 'font-semibold' : ''}`}>
          {item.title}
        </span>
        {task?.status === 'generating' && <Loader2 size={12} className="text-primary animate-spin shrink-0" />}
        {task?.status === 'queued' && <RefreshCw size={12} className="text-slate-400 shrink-0" />}
        {task?.status === 'error' && <AlertCircle size={12} className="text-red-500 shrink-0" />}
        {(item.status === 'completed' || task?.status === 'success') && <CheckCircle2 size={12} className="text-emerald-500 shrink-0" />}
      </div>
      
      {hasChildren && isExpanded && (
        <div className="ml-4 border-l border-slate-100 pl-1 space-y-0.5">
          {item.children!.map(child => (
            <TreeItem 
              key={child.id} 
              item={child} 
              activeId={activeId} 
              onSelect={onSelect} 
              expandedIds={expandedIds} 
              toggleExpand={toggleExpand} 
              taskQueue={taskQueue}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// Mock Data
const MOCK_FLAT_OUTLINE: OutlineItem[] = [
  { id: "1", title: "第一章 公司实力与资质", status: "completed", level: 1 },
  { id: "2", title: "第二章 数字化转型技术方案", level: 1 },
  { id: "2.1", title: "2.1 整体架构设计", status: "in-progress", level: 2 },
  { id: "2.2", title: "2.2 核心模块实现方案", status: "todo", level: 2 },
  { id: "2.3", title: "2.3 数据安全保障", status: "todo", level: 2 },
  { id: "3", title: "第三章 项目实施与交付计划", status: "todo", level: 1 },
];

export default function Dashboard() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "您好！流程已就绪。请先上传【招标文件】供我分析要求，再上传【投标文件底稿】，我将提取底稿大纲作为我们的主工作台。" }
  ]);
  const [input, setInput] = useState("");
  const [flatOutline, setFlatOutline] = useState<OutlineItem[]>(MOCK_FLAT_OUTLINE);
  const [uploading, setUploading] = useState(false);
  const [isCommanding, setIsCommanding] = useState(false);
  const [activeChapterId, setActiveChapterId] = useState<string>("2.1");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set(["2"]));
  const [taskQueue, setTaskQueue] = useState<Record<string, GenTask>>({});
  const [isTaskPanelOpen, setIsTaskPanelOpen] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const MAX_CONCURRENT_TASKS = 3;
  const [isExporting, setIsExporting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const contentAreaRef = useRef<HTMLDivElement>(null);
  const [uploadType, setUploadType] = useState<"tender" | "draft">("tender");

  const treeOutline = useMemo(() => buildTree(flatOutline), [flatOutline]);

  useEffect(() => {
    const fetchLatestProject = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(`${apiUrl}/project/latest`);
        if (response.ok) {
          const data = await response.json();
          if (data.status === "success") {
            setProjectId(data.project_id);
            if (data.outline && data.outline.length > 0) {
              setFlatOutline(data.outline);
              setExpandedIds(new Set(data.outline.filter((n: any) => n.level === 1).map((n: any) => n.id)));
              setMessages(prev => [...prev, { 
                role: "assistant", 
                content: `✅ 已为您恢复最近的工作项目：《${data.filename}》` 
              }]);
            }
          }
        }
      } catch (e) {
        console.error("Failed to load latest project", e);
      }
    };
    fetchLatestProject();
  }, []);


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
          setFlatOutline(prev => {
            const updated = prev.map(item => item.id === chapter.id ? { ...item, content: generatedContent, status: "completed" as const } : item);
            if (projectId) {
              fetch(`${apiUrl}/project/${projectId}/outline`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ outline: updated })
              }).catch(e => console.error("Sync failed", e));
            }
            return updated;
          });
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
  }, [taskQueue, flatOutline, projectId]);

  const toggleExpand = (id: string) => {
    const newExpanded = new Set(expandedIds);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedIds(newExpanded);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (contentAreaRef.current) {
      const viewport = contentAreaRef.current.querySelector('[data-slot="scroll-area-viewport"]');
      if (viewport) {
        viewport.scrollTop = 0;
      }
    }
  }, [activeChapterId]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("上传失败");

      const data = await response.json();
      
      if (uploadType === "draft") {
        if (data.project_id) setProjectId(data.project_id);
        setFlatOutline(data.outline);
        // 默认展开所有一级节点
        setExpandedIds(new Set(data.outline.filter((n: OutlineItem) => n.level === 1).map((n: OutlineItem) => n.id)));
        setMessages(prev => [...prev, { 
          role: "assistant", 
          content: `✅ 已成功解析底稿《${file.name}》，共提取 ${data.outline.length} 个章节。目录树已严格对标 Word 结构。` 
        }]);
      } else {
        setMessages(prev => [...prev, { 
          role: "assistant", 
          content: `✅ 已收到招标文件《${file.name}》，正在分析关键要求...` 
        }]);
      }
    } catch (error) {
      console.error("Upload error:", error);
      setMessages(prev => [...prev, { role: "assistant", content: "❌ 文件解析失败，请检查后端服务是否启动或网络连接是否正常。" }]);
    } finally {
      setUploading(false);
      if (event.target) event.target.value = "";
    }
  };

  const triggerUpload = (type: "tender" | "draft") => {
    setUploadType(type);
    fileInputRef.current?.click();
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isCommanding) return;
    const userInstruction = input;
    setMessages(prev => [...prev, { role: "user", content: userInstruction }]);
    setInput("");
    
    if (flatOutline.length === 0) {
      setMessages(prev => [...prev, { role: "assistant", content: "⚠️ 请先上传投标底稿，我需要先掌握当前的大纲结构。" }]);
      return;
    }

    setIsCommanding(true);
    // Don't add a hardcoded text message. The stream will fill the next message.

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/commander/rewrite-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: userInstruction,
          active_chapter_id: activeChapterId,
          current_outline: flatOutline.map(item => ({
            id: item.id,
            title: item.title,
            level: item.level,
            index: parseInt(item.id.split('.').pop() || '0') || 0
          }))
        })
      });

      if (!response.ok) throw new Error("大纲重写请求失败");
      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let streamBuffer = "";
      let fullContent = "🧠 主脑思考中...\n\n";

      // Append an empty assistant message that will be populated by the stream
      setMessages(prev => [...prev, { role: "assistant", content: fullContent }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        streamBuffer += decoder.decode(value, { stream: true });
        
        const parts = streamBuffer.split("\n\n");
        streamBuffer = parts.pop() || "";

        for (const part of parts) {
          if (part.startsWith("data: ")) {
            const dataStr = part.slice(6);
            try {
              const data = JSON.parse(dataStr);
              if (data.error) throw new Error(data.error);
              if (data.chunk) {
                // Filter out the internal time tag from displaying to user
                let chunkText = data.chunk;
                if (chunkText.includes("[TOTAL_TIME:")) {
                   chunkText = chunkText.split("[TOTAL_TIME:")[0];
                }
                
                fullContent += chunkText;
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].content = fullContent;
                  return newMsgs;
                });
              }
            } catch (e) {
              // ignore partial parse errors if any
            }
          }
        }
      }

      // Read remaining buffer if any
      if (streamBuffer.startsWith("data: ")) {
        const dataStr = streamBuffer.slice(6);
        try {
          const data = JSON.parse(dataStr);
          if (data.chunk) {
            fullContent += data.chunk;
          }
        } catch (e) {}
      }

      // Extract JSON and Time
      const jsonMatch = fullContent.match(/```json\n([\s\S]*?)\n```/);
      const timeMatch = fullContent.match(/\[TOTAL_TIME:(.*?)s\]/);
      const timeStr = timeMatch ? timeMatch[1] : "?";

      if (jsonMatch && jsonMatch[1]) {
        const parsedOutline = JSON.parse(jsonMatch[1]);
        if (parsedOutline.outline) {
          setFlatOutline(parsedOutline.outline);
          setExpandedIds(new Set(parsedOutline.outline.filter((n: any) => n.level === 1).map((n: any) => n.id)));
          
          setMessages(prev => [...prev, { 
            role: "assistant", 
            content: `✅ 大纲重构完成！左侧 Word 结构树已自动更新。思考与生成共耗时：${timeStr} 秒。` 
          }]);
        }
      } else {
        throw new Error("模型未返回有效的 JSON 大纲数据");
      }
    } catch (error: any) {
      console.error(error);
      setMessages(prev => [...prev, { 
        role: "assistant", 
        content: `❌ 大纲重构失败: ${error.message}` 
      }]);
    } finally {
      setIsCommanding(false);
    }
  };

  const handleExportOutline = async () => {
    if (flatOutline.length === 0) {
      setMessages(prev => [...prev, { role: "assistant", content: "⚠️ 当前没有大纲数据，无法导出。" }]);
      return;
    }
    
    setIsExporting(true);
    setMessages(prev => [...prev, { role: "assistant", content: "⏳ 正在基于当前目录结构生成空白 Word 文档..." }]);
    
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/export-outline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outline: flatOutline })
      });
      
      if (!response.ok) throw new Error("导出失败");
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = "投标文件_结构框架.docx";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setMessages(prev => [...prev, { role: "assistant", content: "✅ Word 空白框架文档生成成功！已为您开始下载，它的目录和层级已经严格对标最新大纲。" }]);
    } catch (error: any) {
      console.error(error);
      setMessages(prev => [...prev, { role: "assistant", content: `❌ 导出失败: ${error.message}` }]);
    } finally {
      setIsExporting(false);
    }
  };

  const currentChapter = flatOutline.find(item => item.id === activeChapterId);
  const currentChapterTitle = currentChapter?.title || "未选择章节";

  return (
    <div className="flex h-screen w-full bg-slate-50/50 overflow-hidden font-sans fixed inset-0">
      {/* 左侧栏：可折叠大纲树 */}
      <aside className="w-72 border-r bg-white flex flex-col min-h-0">
        <div className="p-4 border-b flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <div className="bg-primary text-white p-1.5 rounded-md shadow-sm">
              <FileText size={20} />
            </div>
            <span className="font-bold text-lg tracking-tight text-slate-800">BidMaster</span>
          </div>
          <Button variant="ghost" size="icon" className="text-slate-500 hover:text-slate-700">
            <Settings size={18} />
          </Button>
        </div>
        
        <div className="p-4 shrink-0">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <Input placeholder="搜索目录层级..." className="pl-9 bg-slate-100/50 border-transparent focus:bg-white focus:border-primary/30 transition-colors h-9 text-sm" />
          </div>
        </div>

        <ScrollArea className="flex-1 px-3 min-h-0">
          <div className="space-y-1 py-2">
            <div className="px-2 mb-3 flex items-center justify-between">
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Word 目录结构
              </h2>
              <Badge variant="outline" className="text-[10px] h-4 px-1.5 bg-slate-50 text-slate-500 border-slate-200 font-normal">严格对标</Badge>
            </div>
            {treeOutline.map((item) => (
              <TreeItem 
                key={item.id} 
                item={item} 
                activeId={activeChapterId} 
                onSelect={setActiveChapterId} 
                expandedIds={expandedIds}
                toggleExpand={toggleExpand}
                taskQueue={taskQueue}
              />
            ))}
            <Button variant="outline" className="w-full justify-start gap-2 border-dashed mt-4 text-slate-500 hover:text-slate-700 hover:border-slate-300">
              <Plus size={14} />
              <span>插入新层级</span>
            </Button>
          </div>
        </ScrollArea>
        
        <div className="p-4 border-t mt-auto bg-slate-50/30 shrink-0">
          <div className="flex items-center gap-3">
            <Avatar className="h-9 w-9 border shadow-sm">
              <AvatarImage src="" />
              <AvatarFallback className="bg-primary/10 text-primary font-medium">张三</AvatarFallback>
            </Avatar>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-slate-700">张三 (投标经理)</span>
              <span className="text-xs text-slate-500">数字化转型事业部</span>
            </div>
          </div>
        </div>
      </aside>

      {/* 中间主区：双文件管理与底稿编辑 */}
      <main className="flex-1 flex flex-col min-w-0 bg-slate-50 min-h-0">
        <header className="h-16 border-b bg-white flex items-center justify-between px-6 shadow-sm z-10 shrink-0">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-bold text-slate-800 truncate max-w-md">2026年某银行数字化转型咨询服务采购项目</h1>
            <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-blue-100 font-medium">解析层级: {flatOutline.length}</Badge>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" className="gap-2 border-slate-200 text-slate-600 hover:bg-slate-50" onClick={() => triggerUpload("draft")}>
              <Upload size={16} />
              <span>更新底稿</span>
            </Button>
            <Button 
              size="sm" 
              className="shadow-sm"
              onClick={handleExportOutline}
              disabled={isExporting}
            >
              {isExporting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <FileText className="h-4 w-4 mr-2" />}
              生成空白文档
            </Button>
          </div>
        </header>

        <ScrollArea className="flex-1 min-h-0" ref={contentAreaRef}>
          <div className="p-6">
            <div className="max-w-4xl mx-auto space-y-8 pb-12">
              <input 
                type="file" 
                className="hidden" 
                ref={fileInputRef} 
                onChange={handleFileUpload}
                accept=".docx"
              />
              
              <section className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="border-2 border-dashed border-slate-200 rounded-2xl p-6 bg-white hover:border-primary/40 hover:shadow-md transition-all group relative cursor-pointer" onClick={() => !uploading && triggerUpload("tender")}>
                  <div className="flex items-center gap-4">
                    <div className="bg-blue-50/80 p-3 rounded-xl text-blue-600 shadow-sm">
                      <FileText size={24} />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-sm text-slate-800">招标文件 (甲方)</h3>
                      <p className="text-xs text-slate-500 mt-1">上传后 AI 将自动对标要求</p>
                    </div>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="w-full mt-5 bg-slate-50 border-none group-hover:bg-primary group-hover:text-white transition-all disabled:opacity-50 font-medium text-slate-600"
                    disabled={uploading}
                  >
                    {uploading && uploadType === "tender" ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> 上传解析中...</>
                    ) : "点击上传招标文件"}
                  </Button>
                </div>

                <div className="border-2 border-dashed border-indigo-200 rounded-2xl p-6 bg-white hover:border-indigo-500/40 hover:shadow-md transition-all group relative cursor-pointer" onClick={() => !uploading && triggerUpload("draft")}>
                  <div className="flex items-center gap-4">
                    <div className="bg-indigo-50/80 p-3 rounded-xl text-indigo-600 shadow-sm">
                      <Plus size={24} />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-sm text-slate-800">投标文件底稿 (公司)</h3>
                      <p className="text-xs text-slate-500 mt-1">作为扩写的基础大纲</p>
                    </div>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="w-full mt-5 bg-slate-50 border-none group-hover:bg-indigo-600 group-hover:text-white transition-all disabled:opacity-50 font-medium text-slate-600"
                    disabled={uploading}
                  >
                    {uploading && uploadType === "draft" ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> 上传解析中...</>
                    ) : "点击上传投标底稿"}
                  </Button>
                </div>
              </section>

              <section className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold flex items-center gap-2 text-slate-800 text-lg">
                    <div className="h-5 w-1.5 bg-primary rounded-full shadow-sm" />
                    章节扩写工作区
                  </h3>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-medium px-3 py-1 bg-white border-slate-200 text-slate-600 shadow-sm">当前章节: {currentChapterTitle}</Badge>
                  </div>
                </div>

                <Card className="border-slate-200 shadow-md overflow-hidden rounded-2xl">
                  <div className="bg-slate-50/80 px-5 py-3 border-b flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">底稿内容预览 & AI 辅助填充</span>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-8 text-xs gap-1.5 text-primary hover:bg-primary/10 font-medium"
                      onClick={() => enqueueGeneration(activeChapterId)}
                      disabled={(taskQueue[activeChapterId]?.status === 'generating' || taskQueue[activeChapterId]?.status === 'queued')}
                    >
                      {(taskQueue[activeChapterId]?.status === 'generating' || taskQueue[activeChapterId]?.status === 'queued') ? (
                        <><Loader2 className="h-3.5 w-3.5 animate-spin" /> 生成中...</>
                      ) : (
                        <><Plus size={14} /> AI 智能扩写本章</>
                      )}
                    </Button>
                  </div>
                  <CardContent className="p-8 bg-white">
                    <div className="prose prose-slate max-w-none">
                      <h4 className="text-slate-900 font-extrabold text-xl mb-6">{currentChapterTitle}</h4>
                      <div className="text-slate-600 leading-relaxed min-h-[200px] whitespace-pre-wrap">
                        {(taskQueue[activeChapterId]?.status === 'generating' || taskQueue[activeChapterId]?.status === 'queued') ? (
                          <div className="flex flex-col items-center justify-center h-48 space-y-4 text-slate-400">
                            <Loader2 className="h-8 w-8 animate-spin text-primary/60" />
                            <p>AI 正在奋笔疾书，预计需要几十秒时间...</p>
                          </div>
                        ) : currentChapter?.content ? (
                          <p>{currentChapter.content}</p>
                        ) : activeChapterId === "2.1" ? (
                          <p>
                            本项目的整体架构遵循“高可用、可扩展、安全性”的设计原则。底座采用私有云部署，支撑上层业务应用。前端采用微前端架构，后端基于 Spring Cloud 微服务体系，实现业务解耦与敏捷交付...
                          </p>
                        ) : (
                          <p className="text-slate-400 italic">此章节内容为空，请点击上方「AI 智能扩写本章」基于底稿和招标文件要求自动生成内容。</p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </section>
            </div>
          </div>
        </ScrollArea>
      
      {/* 任务监控悬浮窗与按钮 (Bottom Right Drawer) */}
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
      </div>
</main>


      {/* 右侧栏：AI 对话 */}
      <aside className="w-80 border-l bg-white flex flex-col shadow-[0_0_40px_-15px_rgba(0,0,0,0.1)] z-10 min-h-0">
        <div className="p-4 border-b flex items-center gap-3 bg-slate-50/50 shrink-0">
          <div className="bg-indigo-600 text-white p-2 rounded-xl shadow-sm">
            <MessageSquare size={18} />
          </div>
          <div>
            <h2 className="font-bold text-[15px] leading-tight text-slate-800">AI 指挥官</h2>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-[10px] text-emerald-600 font-medium tracking-wide">在线已就绪</span>
            </div>
          </div>
        </div>

        <ScrollArea className="flex-1 min-h-0 bg-slate-50/30">
          <div className="p-4 space-y-5 pb-4">
            {messages.map((m, idx) => (
              <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm leading-relaxed ${
                  m.role === 'user' 
                  ? 'bg-primary text-white rounded-tr-sm' 
                  : 'bg-white border border-slate-100 text-slate-700 rounded-tl-sm'
                }`}>
                  {m.content}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <div className="p-4 border-t bg-white shrink-0">
          <div className="relative group">
            <Input 
              placeholder="询问如何扩写底稿..." 
              className="pr-12 h-12 bg-slate-50 border-slate-200 focus-visible:ring-1 focus-visible:ring-primary focus-visible:bg-white transition-all rounded-xl"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            />
            <Button 
              size="icon" 
              className="absolute right-1.5 top-1.5 h-9 w-9 rounded-lg bg-primary hover:bg-primary/90 shadow-sm"
              onClick={handleSendMessage}
              disabled={!input.trim() || isCommanding}
            >
              <Send size={16} className={(!input.trim() || isCommanding) ? "opacity-50" : ""} />
            </Button>
          </div>
          <p className="text-[10px] text-center text-slate-400 mt-3 uppercase tracking-widest font-semibold flex items-center justify-center gap-1.5">
            <span className="h-px w-4 bg-slate-200"></span>
            Powered by Gemini Pro
            <span className="h-px w-4 bg-slate-200"></span>
          </p>
        </div>
      </aside>
    </div>
  );
}