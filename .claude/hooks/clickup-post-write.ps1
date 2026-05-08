# PostToolUse hook — triggered after every Write call.
# Handles ClickUp task creation/updates when speckit writes spec.md or plan.md.
# Credentials are loaded from .env.clickup in the project root (gitignored).

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

# Load credentials from .env.clickup
$envFile = ".env.clickup"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([A-Za-z_][A-Za-z0-9_]*)=(.+)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim())
        }
    }
}

$token  = $env:CLICKUP_API_TOKEN
$listId = $env:CLICKUP_LIST_ID

if (-not $token -or -not $listId) {
    Write-Warning "ClickUp hook: CLICKUP_API_TOKEN or CLICKUP_LIST_ID not set in .env.clickup — skipping."
    exit 0
}

$headers = @{ "Authorization" = $token; "Content-Type" = "application/json" }

function Invoke-CU { param($method, $path, $body)
    $uri    = "https://api.clickup.com/api/v2$path"
    $params = @{ Uri = $uri; Method = $method; Headers = $headers; ErrorAction = "Stop" }
    if ($body) { $params.Body = ($body | ConvertTo-Json -Compress -Depth 5) }
    return Invoke-RestMethod @params
}

function Find-CUTask($name) {
    try {
        $enc  = [uri]::EscapeDataString($name)
        $resp = Invoke-CU GET "/list/$listId/task?search=$enc&include_closed=false"
        return $resp.tasks | Where-Object { $_.name -eq $name } | Select-Object -First 1
    } catch { return $null }
}

function Find-CUSubtask($parentId, $subtaskName) {
    try {
        $resp = Invoke-CU GET "/task/${parentId}?include_subtasks=true"
        return $resp.subtasks | Where-Object { $_.name -eq $subtaskName } | Select-Object -First 1
    } catch { return $null }
}

# "001-k8s-cdc-event-generator" → "001 k8s cdc event generator"
function Format-FeatureName($folder) { return ($folder -replace '-', ' ') }

# ── Post-Specify ──────────────────────────────────────────────────────────────
if ($specMatch.Success) {
    $folder      = $specMatch.Groups[1].Value
    $featureName = Format-FeatureName $folder

    # Skip if already tracked in frontmatter
    if ((Test-Path $filePath) -and ((Get-Content $filePath -Raw) -match 'clickup_task_id')) { exit 0 }
    # Skip if task already exists in ClickUp
    if (Find-CUTask $featureName) { exit 0 }

    # Extract one-sentence goal from spec
    $goal = ""
    if (Test-Path $filePath) {
        foreach ($line in (Get-Content $filePath)) {
            if ($line -match '^\s*\*\*Goal\*\*:?\s*(.+)' -or $line -match '^\s*Goal:?\s*(.+)') {
                $goal = $matches[1]; break
            }
        }
    }

    $specUrl     = "https://github.com/GustavoBertaco/agent-harness-experiment/tree/main/specs/$folder/"
    $description = if ($goal) { "$goal`n$specUrl" } else { $specUrl }

    try {
        $parent    = Invoke-CU POST "/list/$listId/task" @{
            name        = $featureName
            description = $description
            status      = "to do"
            tags        = @("spec", "pending-review")
        }
        $discovery = Invoke-CU POST "/list/$listId/task" @{
            name   = "Discovery"
            status = "to do"
            tags   = @("discovery")
            parent = $parent.id
        }
        Write-Output "ClickUp: parent task -> $($parent.url)"
        Write-Output "ClickUp: Discovery subtask -> $($discovery.url)"
    } catch {
        Write-Warning "ClickUp post-specify hook error: $_"
    }
    exit 0
}

# ── Post-Plan ────────────────────────────────────────────────────────────────
if ($planMatch.Success) {
    $folder      = $planMatch.Groups[1].Value
    $featureName = Format-FeatureName $folder
    $planUrl     = "https://github.com/GustavoBertaco/agent-harness-experiment/tree/main/specs/$folder/plan.md"

    $parent = Find-CUTask $featureName
    if (-not $parent) {
        Write-Warning "ClickUp post-plan hook: no parent task found for '$featureName' — skipping."
        exit 0
    }

    $discovery = Find-CUSubtask $parent.id "Discovery"
    if ($discovery) {
        try {
            Invoke-CU PUT "/task/$($discovery.id)" @{
                status      = "complete"
                description = "Architecture and implementation plan created.`n$planUrl"
            } | Out-Null
        } catch { Write-Warning "ClickUp: could not update Discovery subtask: $_" }
    }

    try {
        $refinement = Invoke-CU POST "/list/$listId/task" @{
            name   = "Refinement"
            status = "to do"
            tags   = @("refinement")
            parent = $parent.id
        }
        Invoke-CU PUT "/task/$($parent.id)" @{ status = "planning" } | Out-Null
        Write-Output "ClickUp: Discovery -> complete, Refinement -> $($refinement.url), parent -> planning"
    } catch {
        Write-Warning "ClickUp post-plan hook error: $_"
    }
}

# ── Post-Tasks ────────────────────────────────────────────────────────────────
if ($tasksMatch.Success) {
    $folder      = $tasksMatch.Groups[1].Value
    $featureName = Format-FeatureName $folder

    $parent = Find-CUTask $featureName
    if (-not $parent) {
        Write-Warning "ClickUp post-tasks hook: no parent task found for '$featureName' — skipping."
        exit 0
    }

    # Move Refinement subtask to complete
    $refinement = Find-CUSubtask $parent.id "Refinement"
    if ($refinement -and $refinement.status.status -ne "complete") {
        try {
            Invoke-CU PUT "/task/$($refinement.id)" @{ status = "complete" } | Out-Null
            Write-Output "ClickUp: Refinement -> complete"
        } catch { Write-Warning "ClickUp: could not update Refinement subtask: $_" }
    }

    # Parse phases and their tasks from tasks.md
    if (-not (Test-Path $filePath)) { exit 0 }

    $phases      = [System.Collections.ArrayList]@()
    $currentPhase = $null

    foreach ($line in (Get-Content $filePath)) {
        if ($line -match '^## Phase \d+[:\s]+(.+)$') {
            $currentPhase = @{ Name = $matches[1].Trim(); Tasks = [System.Collections.ArrayList]@() }
            [void]$phases.Add($currentPhase)
        }
        elseif ($null -ne $currentPhase -and $line -match '^- \[ \] \w+\s+(?:\[P\]\s+)?(?:\[\w+\]\s+)?(.+)$') {
            [void]$currentPhase.Tasks.Add($matches[1].Trim())
        }
    }

    foreach ($phase in $phases) {
        # Idempotent: skip if phase subtask already exists
        $phaseTask = Find-CUSubtask $parent.id $phase.Name
        if (-not $phaseTask) {
            try {
                $phaseTask = Invoke-CU POST "/list/$listId/task" @{
                    name   = $phase.Name
                    status = "backlog"
                    tags   = @("phase")
                    parent = $parent.id
                }
                Write-Output "ClickUp: Phase -> $($phaseTask.url)"
            } catch {
                Write-Warning "ClickUp: could not create phase '$($phase.Name)': $_"
                continue
            }
        }

        foreach ($taskName in $phase.Tasks) {
            $existingTask = Find-CUSubtask $phaseTask.id $taskName
            if (-not $existingTask) {
                try {
                    $cuTask = Invoke-CU POST "/list/$listId/task" @{
                        name   = $taskName
                        status = "backlog"
                        parent = $phaseTask.id
                    }
                    Write-Output "ClickUp: Task -> $($cuTask.url)"
                } catch {
                    Write-Warning "ClickUp: could not create task '$taskName': $_"
                }
            }
        }
    }
}
