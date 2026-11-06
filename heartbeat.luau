-- Execute no seu cliente com suporte a request HTTP local.
local url = "__HEARTBEAT_URL__"
local key = "__HEARTBEAT_KEY__"
local player = game:GetService("Players").LocalPlayer
local http = game:GetService("HttpService")
local send = request or http_request or (syn and syn.request)
assert(player and send, "Rejoin Desk: ambiente sem HTTP local ou jogador indisponível")
local env = getgenv and getgenv() or _G
local teleport = game:GetService("TeleportService")
local session = http:GenerateGUID(false)
env.RejoinDeskHeartbeat = session
local readySince = nil
local nextMove = 0
local moving = false
local moveStarted = 0
local targetJob = ""
local failedJob = ""
local attempts = 0

local function moveFailed()
    failedJob = targetJob
    moving = false
    nextMove = os.clock() + (attempts >= 3 and 60 or 15)
    if attempts >= 3 then attempts = 0 end
    warn("SK Rejoin • BLOCK ACC: rejoin falhou; nova tentativa após a espera.")
end

local teleportFailure = teleport.TeleportInitFailed:Connect(function(who)
    if who == player and moving and env.RejoinDeskHeartbeat == session then
        moveFailed()
    end
end)
task.spawn(function()
    while env.RejoinDeskHeartbeat == session do
        local now = os.clock()
        local character = player.Character
        local loaded = game:IsLoaded() and character and character:FindFirstChild("HumanoidRootPart")
        if loaded then
            readySince = readySince or now
        else
            readySince = nil
        end
        local ready = readySince ~= nil and now - readySince >= 10
        if moving and now - moveStarted >= 30 then moveFailed() end
        local ok, response = pcall(send, {
            Url = url, Method = "POST",
            Headers = {["Content-Type"] = "application/json", ["X-Heartbeat-Key"] = key},
            Body = http:JSONEncode({
                userId = player.UserId, placeId = game.PlaceId, jobId = game.JobId,
                session = session, readyForBlock = ready, failedJobId = failedJob
            })
        })
        if ok and response and response.StatusCode == 200 and env.RejoinDeskHeartbeat == session then
            local parsed, data = pcall(http.JSONDecode, http, response.Body)
            if parsed and type(data) == "table" then
                local move = data.relocate
                if ready and not moving and os.clock() >= nextMove and type(move) == "table"
                    and move.placeId == game.PlaceId and type(move.jobId) == "string"
                    and move.jobId ~= game.JobId then
                    targetJob = move.jobId
                    attempts = attempts + 1
                    moving = true
                    moveStarted = os.clock()
                    nextMove = moveStarted + 15
                    local moved = pcall(function()
                        teleport:TeleportToPlaceInstance(move.placeId, move.jobId, player)
                    end)
                    if not moved then moveFailed() end
                end
            end
        end
        task.wait(5)
    end
    teleportFailure:Disconnect()
end)
