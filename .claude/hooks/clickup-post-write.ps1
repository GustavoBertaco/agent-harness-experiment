# PostToolUse hook — triggered after every Write call.
# Detects speckit output files and asks Claude to use the ClickUp MCP.
# No credentials needed — all ClickUp calls go through the MCP in-session.

$stdinContent = [Console]::In.ReadToEnd()
if (-not $stdinContent) { exit 0 }

try { $data = $stdinContent | ConvertFrom-Json } catch { exit 0 }

$filePath = $data.tool_input.file_path
if (-not $filePath) { exit 0 }

$filePath = $filePath -replace '\\', '/'

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
