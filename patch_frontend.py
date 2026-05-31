import re
import sys

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# 1. Add projectId state
state_old = "const [isTaskPanelOpen, setIsTaskPanelOpen] = useState(false);"
state_new = "const [isTaskPanelOpen, setIsTaskPanelOpen] = useState(false);\n  const [projectId, setProjectId] = useState<string | null>(null);"
content = content.replace(state_old, state_new)

# 2. Add useEffect for initialization
init_effect = """
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
"""
# Insert after treeOutline useMemo
content = content.replace("const treeOutline = useMemo(() => buildTree(flatOutline), [flatOutline]);", "const treeOutline = useMemo(() => buildTree(flatOutline), [flatOutline]);\n" + init_effect)

# 3. Handle upload project_id capture
upload_success_old = """if (uploadType === "draft") {
        setFlatOutline(data.outline);"""
upload_success_new = """if (uploadType === "draft") {
        if (data.project_id) setProjectId(data.project_id);
        setFlatOutline(data.outline);"""
content = content.replace(upload_success_old, upload_success_new)

# 4. Handle sync to backend on generate success
gen_success_old = """setFlatOutline(prev => prev.map(item => item.id === chapter.id ? { ...item, content: generatedContent, status: "completed" } : item));"""
gen_success_new = """setFlatOutline(prev => {
            const updated = prev.map(item => item.id === chapter.id ? { ...item, content: generatedContent, status: "completed" } : item);
            if (projectId) {
              fetch(`${apiUrl}/project/${projectId}/outline`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ outline: updated })
              }).catch(e => console.error("Sync failed", e));
            }
            return updated;
          });"""
content = content.replace(gen_success_old, gen_success_new)

# Since we reference projectId in the useEffect for processQueue, we must add it to the dependency array.
dep_old = "}, [taskQueue, flatOutline]);"
dep_new = "}, [taskQueue, flatOutline, projectId]);"
content = content.replace(dep_old, dep_new)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

print("Frontend patched for SQLite.")
