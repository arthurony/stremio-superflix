import requests
import re
import os
from flask import Flask, jsonify
from flask_cors import CORS
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# --- CONFIGURAÇÕES ---
TMDB_API_KEY = "a2302823aa095244b25c628ed1c71807"

class SuperFlixScraper:
    def __init__(self):
        self.base_api = "https://playerflixapi.com" 
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Referer": "https://embedmovies.org/",
            "X-Requested-With": "XMLHttpRequest"
        }

    def get_tmdb_id_from_imdb(self, imdb_id, media_type):
        """Usa sua API Key do TMDB para converter tt12345 em ID numérico"""
        try:
            url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
            res = requests.get(url, timeout=5).json()
            
            if media_type == "movie" and res.get("movie_results"):
                return res["movie_results"][0]["id"]
            elif media_type == "series" and res.get("tv_results"):
                return res["tv_results"][0]["id"]
            return None
        except Exception as e:
            print(f"Erro TMDB API: {e}")
            return None

    def get_player_list(self, tmdb_id, media_type, season=None, episode=None):
        """Busca a lista de players no Superflix"""
        m_type = "tv" if media_type == "series" else "movie"
        url = f"{self.base_api}/pages/ajax.php?id={tmdb_id}&type={m_type}"
        
        if media_type == "series":
            url += f"&season={season}&episode={episode}"
            
        res = requests.get(url, headers=self.headers, timeout=10)
        
        # Regex para capturar links dos players e nomes
        pattern = r'onclick=\'callPlayer\("(https://.*?)",\d+\)\'>.*?class="player-name">(.*?)</span>'
        players = re.findall(pattern, res.text, re.DOTALL)
        
        results = []
        for link, name in players:
            # Filtramos para pegar os players que costumam funcionar melhor (Llanfair/Premium)
            if "llanfair" in link or "fireplayer" in link:
                results.append({"name": name.strip(), "url": link})
        return results

    def get_final_m3u8(self, player_url):
        """Extrai o link final do vídeo .m3u8"""
        try:
            parsed = urlparse(player_url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            video_hash = player_url.split('/')[-1]
            
            api_url = f"{domain}/player/index.php?data={video_hash}&do=getVideo"
            payload = {"hash": video_hash, "r": ""}
            
            post_headers = self.headers.copy()
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"
            post_headers["Referer"] = player_url

            res = requests.post(api_url, data=payload, headers=post_headers, timeout=10)
            data = res.json()
            return data.get("securedLink")
        except:
            return None

scraper = SuperFlixScraper()

# --- ROTAS DO STREMIO ---

MANIFEST = {
    "id": "br.superflix.vip.addon",
    "version": "1.0.2",
    "name": "SuperFlix VIP",
    "description": "Filmes e Séries via API (Links Diretos)",
    "logo": "https://superflixapi.run/img/favicon/192.png?v=v2.5",
    "resources": [
        {
            "name": "stream",
            "types": ["movie", "series"],
            "idPrefixes": ["tt"]
        }
    ],
    "types": ["movie", "series"],
    "catalogs": [],  
    "behaviorHints": {
        "configurable": False,
        "configurationRequired": False
    }
}

@app.route('/manifest.json')
def manifest():
    return jsonify(MANIFEST)

@app.route('/stream/<type>/<id>.json')
def stream_handler(type, id):
    streams = []
    
    # Tratamento de ID (tt12345 ou tt12345:1:5)
    parts = id.split(':')
    imdb_id = parts[0]
    season = parts[1] if len(parts) > 1 else None
    episode = parts[2] if len(parts) > 2 else None

    # 1. Converte IMDB -> TMDB
    tmdb_id = scraper.get_tmdb_id_from_imdb(imdb_id, type)
    
    if not tmdb_id:
        return jsonify({"streams": []})

    # 2. Busca Players
    try:
        players = scraper.get_player_list(tmdb_id, type, season, episode)
        
        for p in players:
            m3u8_url = scraper.get_final_m3u8(p['url'])
            if m3u8_url:
                streams.append({
                    "name": "SuperFlix",
                    "title": f"🎬 {p['name']}\nAuto-Res (m3u8)",
                    "url": m3u8_url,
                    "behaviorHints": {
                        "notSupportingExternalPlayer": False
                    }
                })
    except Exception as e:
        print(f"Erro Geral: {e}")

    return jsonify({"streams": streams})

# --- INICIALIZAÇÃO PARA RENDER ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

