# PostToolUse hook — triggered after Write and Edit calls.
# Detects speckit output files and asks Claude to use the ClickUp MCP.
# No credentials needed — all ClickUp calls go through the MCP in-session.

$stdinContent = [Console]::In.ReadToEnd()
if (-not $stdinContent) { exit 0 }

try { $data = $stdinContent | ConvertFrom-Json } catch { exit 0 }

$filePath = $data.tool_input.file_path
if (-not $filePath) { exit 0 }

$filePath = $filePath -replace '\\', '/'

$toolName = $data.tool_name

# ── Edit path: track per-task completion from speckit-implement ──────────────
if ($toolName -eq 'Edit') {
    $tasksEditMatch = [regex]::Match($filePath, 'specs/([^/]+)/tasks\.md$')
    if (-not $tasksEditMatch.Success) { exit 0 }

    $folder      = $tasksEditMatch.Groups[1].Value
    $featureName = ($folder -replace '-', ' ')
    $oldString   = $data.tool_input.old_string
    $newString   = $data.tool_input.new_string

    if (-not $oldString -or -not $newString) { exit 0 }

    $oldLines = $oldString -split "`n"
    $newLines = $newString -split "`n"

    # Collect task IDs that flipped from [ ] to [x] in this edit
    $completedTaskIds = @()
    foreach ($line in $newLines) {
        if ($line -match '^\s*-\s*\[x\]\s+(T\d+)\b') {
            $taskId = $Matches[1]
            $wasIncomplete = $oldLines | Where-Object { $_ -match "^\s*-\s*\[ \]\s+$taskId\b" }
            if ($wasIncomplete) { $completedTaskIds += $taskId }
        }
    }

    if ($completedTaskIds.Count -gt 0) {
        $taskList = $completedTaskIds -join ', '
        Write-Output "ClickUp post-implement: task(s) $taskList in feature '$featureName' were just marked complete by speckit-implement. Use the ClickUp MCP to: (1) find the parent ClickUp task named '$featureName'; (2) read specs/$folder/tasks.md to identify which Phase each completed task ID belongs to; (3) for each affected Phase, if ALL tasks in that Phase are now marked [x], update the corresponding Phase subtask in ClickUp to status 'complete'; (4) if only some tasks in the Phase are done, update the Phase subtask to 'in progress' if it is currently 'backlog'."
    }
    exit 0
}

# ── Write path: spec-kit lifecycle hooks ─────────────────────────────────────
$specMatch  = [regex]::Match($filePath, 'specs/([^/]+)/spec\.md$')
$planMatch  = [regex]::Match($filePath, 'specs/([^/]+)/plan\.md$')
$tasksMatch = [regex]::Match($filePath, 'specs/([^/]+)/tasks\.md$')

if (-not $specMatch.Success -and -not $planMatch.Success -and -not $tasksMatch.Success) { exit 0 }

if ($specMatch.Success) {
    $folder      = $specMatch.Groups[1].Value
    $featureName = ($folder -replace '-', ' ')
    Write-Output "ClickUp post-specify: use the ClickUp MCP to create a parent task named '$featureName' (status: to do, tags: spec + pending-review) and a 'Discovery' subtask (status: to do, tag: discovery) in the configured list. Skip silently if the task already exists."
}

if ($planMatch.Success) {
    $folder      = $planMatch.Groups[1].Value
    $featureName = ($folder -replace '-', ' ')
    Write-Output "ClickUp post-plan: use the ClickUp MCP to find the parent task named '$featureName', mark its 'Discovery' subtask complete, create a 'Refinement' subtask (status: to do, tag: refinement), and move the parent task to 'planning' status."
}

if ($tasksMatch.Success) {
    $folder      = $tasksMatch.Groups[1].Value
    $featureName = ($folder -replace '-', ' ')
    Write-Output "ClickUp post-tasks: use the ClickUp MCP to find the parent task named '$featureName', mark its 'Refinement' subtask complete, then read specs/$folder/tasks.md and create one subtask per phase (Phase 1 through the final phase) under the parent task with status 'backlog'."
}
