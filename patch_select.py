import sys

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# 1. Inject handleSelectChapter
target_insert = "const cancelTask = (chapterId: string) => {"
new_function = """const handleSelectChapter = (chapterId: string) => {
    setActiveChapterId(chapterId);
    
    const chapterIndex = flatOutline.findIndex(c => c.id === chapterId);
    if (chapterIndex !== -1 && chapterIndex + 1 < flatOutline.length) {
      if (flatOutline[chapterIndex + 1].level > flatOutline[chapterIndex].level) {
        // If it's a non-leaf node, auto-submit its leaves
        enqueueGeneration(chapterId);
      }
    }
  };

  """
content = content.replace(target_insert, new_function + target_insert)

# 2. Update TreeItem onSelect binding
tree_binding_old = """<TreeItem 
                key={item.id} 
                item={item} 
                activeId={activeChapterId} 
                onSelect={setActiveChapterId} 
                expandedIds={expandedIds}
                toggleExpand={toggleExpand}
                taskQueue={taskQueue}
              />"""
tree_binding_new = """<TreeItem 
                key={item.id} 
                item={item} 
                activeId={activeChapterId} 
                onSelect={handleSelectChapter} 
                expandedIds={expandedIds}
                toggleExpand={toggleExpand}
                taskQueue={taskQueue}
              />"""
content = content.replace(tree_binding_old, tree_binding_new)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

print("Patch handleSelectChapter applied.")
