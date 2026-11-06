-- Execute no seu cliente com suporte a request HTTP local.
local url = "__HEARTBEAT_URL__"
local key = "__HEARTBEAT_KEY__"
local player = game:GetService("Players").LocalPlayer
local http = game:GetService("HttpService")
local send = request or http_request or (syn and syn.request)
assert(player and send, "Rejoin Desk: ambiente sem HTTP local ou jogador indisponível")
local env = getgenv and getgenv() or _G
local teleport = game:GetService("TeleportService")
local lastMove = -math.huge
local moving = false
local session = http:GenerateGUID(false)
env.RejoinDeskHeartbeat = session
local teleportFailure = teleport.TeleportInitFailed:Connect(function(who)
    if who == player and moving and env.RejoinDeskHeartbeat == session then
        env.RejoinDeskHeartbeat = nil
        player:Kick("SK Rejoin • BLOCK ACC: a troca de servidor falhou. Confira a conta no app.")
    end
end)
task.spawn(function()
    while env.RejoinDeskHeartbeat == session do
        local ok, response = pcall(send, {
            Url = url, Method = "POST",
            Headers = {["Content-Type"] = "application/json", ["X-Heartbeat-Key"] = key},
            Body = http:JSONEncode({userId = player.UserId, placeId = game.PlaceId, jobId = game.JobId, session = session})
        })
        if ok and response and response.StatusCode == 200 and env.RejoinDeskHeartbeat == session then
            local parsed, data = pcall(http.JSONDecode, http, response.Body)
            if parsed and type(data) == "table" then
                if type(data.stop) == "string" then
                    env.RejoinDeskHeartbeat = nil
                    player:Kick(data.stop)
                    break
                end
                local move = data.relocate
                if type(move) == "table" and move.placeId == game.PlaceId and type(move.jobId) == "string"
                    and move.jobId ~= game.JobId and os.clock() - lastMove >= 15 then
                    lastMove = os.clock()
                    moving = true
                    local moved = pcall(function()
                        teleport:TeleportToPlaceInstance(move.placeId, move.jobId, player)
                    end)
                    if not moved then
                        env.RejoinDeskHeartbeat = nil
                        player:Kick("SK Rejoin • BLOCK ACC: não foi possível trocar de servidor.")
                        break
                    end
                end
            end
        end
        task.wait(5)
    end
    teleportFailure:Disconnect()
end)
