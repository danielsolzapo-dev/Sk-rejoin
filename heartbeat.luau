-- Execute no seu cliente com suporte a request HTTP local.
local url = "__HEARTBEAT_URL__"
local key = "__HEARTBEAT_KEY__"
local player = game:GetService("Players").LocalPlayer
local http = game:GetService("HttpService")
local send = request or http_request or (syn and syn.request)
assert(player and send, "Rejoin Desk: ambiente sem HTTP local ou jogador indisponível")
local env = getgenv and getgenv() or _G
local session = http:GenerateGUID(false)
env.RejoinDeskHeartbeat = session
task.spawn(function()
    while env.RejoinDeskHeartbeat == session do
        pcall(send, {
            Url = url, Method = "POST",
            Headers = {["Content-Type"] = "application/json", ["X-Heartbeat-Key"] = key},
            Body = http:JSONEncode({userId = player.UserId, placeId = game.PlaceId, session = session})
        })
        task.wait(5)
    end
end)
