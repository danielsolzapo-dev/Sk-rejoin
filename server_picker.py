"""Bounded public-server discovery. Account sessions are never sent to this API."""
import json
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

JOB = re.compile(r'[A-Za-z0-9-]{1,80}\Z')
LOCK = threading.Lock()
CACHE = {}


def candidates(place):
    if type(place) is not int or not 0 < place < 10**16:
        raise ValueError('Place ID inválido para BLOCK ACC.')
    with LOCK:
        cached = CACHE.get(place)
        if cached and time.monotonic() - cached[0] < 60:
            return cached[1].copy()
        result = []
        cursor = ''
        try:
            for _ in range(3):
                query = {'sortOrder': 'Asc', 'limit': 100, 'excludeFullGames': 'true'}
                if cursor:
                    query['cursor'] = cursor
                url = f'https://games.roblox.com/v1/games/{place}/servers/Public?' + urlencode(query)
                with urlopen(Request(url, headers={'User-Agent': 'SK-Rejoin'}), timeout=10) as response:
                    raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise ValueError('Lista de servidores acima do limite.')
                data = json.loads(raw)
                if not isinstance(data, dict) or not isinstance(data.get('data'), list):
                    raise ValueError('O Roblox não retornou uma lista de servidores válida.')
                for row in data['data'][:100]:
                    if not isinstance(row, dict):
                        continue
                    job, playing, capacity = row.get('id'), row.get('playing'), row.get('maxPlayers')
                    if isinstance(job, str) and JOB.fullmatch(job) and type(playing) is int and type(capacity) is int and 0 <= playing < capacity:
                        result.append(job)
                if result:
                    break
                cursor = data.get('nextPageCursor')
                if not isinstance(cursor, str) or not cursor or len(cursor) > 1024:
                    break
        except HTTPError as error:
            if error.code == 429:
                raise ValueError('Roblox limitou a consulta de servidores. Aguarde antes de tentar BLOCK ACC novamente.') from None
            raise ValueError('Não foi possível consultar os servidores deste jogo.') from None
        except (OSError, URLError):
            raise ValueError('Consulta de servidores indisponível. BLOCK ACC aguarda uma nova tentativa.') from None
        CACHE[place] = (time.monotonic(), list(dict.fromkeys(result)))
        if len(CACHE) > 30:
            del CACHE[next(iter(CACHE))]
        return CACHE[place][1].copy()
