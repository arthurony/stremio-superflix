import requests
import re
import os
from flask import Flask, jsonify
from flask_cors import CORS
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = "a2302823aa095244b25c628ed1c71807"

class SuperFlixScraper:
    def __init__(self):
        # Usando o domínio que funcionou no seu teste local
        self.base_api = "https://playerflixapi.com" 
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://embedmovies.org/",
            "X-Requested-With": "XMLHttpRequest"
        }

    def get_tmdb_id(self, imdb_id, media_type):
        try:
            url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
            res = requests.get(url, timeout=10).json()
            if media_type == "movie" and res.get("movie_results"):
                return res["movie_results"][0]["id"]
            elif media_type == "series" and res.get("tv_results"):
                return res["tv_results"][0]["id"]
            return None
        except: return None

    def get_player_list(self, tmdb_id, media_type, season=None, episode=None):
        m_type = "tv" if media_type == "series" else "movie"
        url = f"{self.base_api}/pages/ajax.php?id={tmdb_id}&type={m_type}"
        if media_type == "series":
            url += f"&season={season}&episode={episode}"
            
        res = requests.get(url, headers=self.headers, timeout=10)
        # Regex flexível que funcionou no seu teste
        pattern = r'callPlayer\s*\(\s*["\'](https?://.*?)["\']\s*,\s*\d+\s*\).*?class=["\']player-name["\']>(.*?)</span>'
        return re.findall(pattern, res.text, re.DOTALL | re.IGNORECASE)

    def get_final_m3u8(self, player_url):
        try:
            video_hash = player_url.split('/')[-1]
            parsed = urlparse(player_url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            api_url = f"{domain}/player/index.php?data={video_hash}&do=getVideo"
            
            headers = self.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Referer"] = player_url

            res = requests.post(api_url, data={"hash": video_hash, "r": ""}, headers=headers, timeout=10)
            return res.json().get("securedLink")
        except: return None

scraper = SuperFlixScraper()

MANIFEST = {
    "id": "br.superflix.vip.oficial",
    "version": "1.1.0",
    "name": "SuperFlix VIP",
    "description": "Canais de Filmes e Séries Dublados",
    "resources": [{"name": "stream", "types": ["movie", "series"], "idPrefixes": ["tt"]}],
    "types": ["movie", "series"],
    "catalogs": []
}

@app.route('/manifest.json')
def manifest():
    return jsonify(MANIFEST)

@app.route('/stream/<type>/<id>.json')
def stream_handler(type, id):
    streams = []
    parts = id.split(':')
    imdb_id = parts[0]
    season = parts[1] if len(parts) > 1 else None
    episode = parts[2] if len(parts) > 2 else None

    tmdb_id = scraper.get_tmdb_id(imdb_id, type)
    if tmdb_id:
        players = scraper.get_player_list(tmdb_id, type, season, episode)
        for link, name in players:
            m3u8 = scraper.get_final_m3u8(link)
            if m3u8:
                # O Pulo do Gato: BehaviorHints para o player não dar erro
                streams.append({
                    "name": "SuperFlix",
                    "title": f"🎬 {name.strip()}\nAuto-Res (m3u8)",
                    "url": m3u8,
                    "behaviorHints": {
                        "notSupportingExternalPlayer": False,
                        "proxyHeaders": {
                            "request": {
                                "Referer": "https://llanfairpwllgwyngy.com/",
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            }
                        }
                    }
                })
    
    return jsonify({"streams": streams})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
