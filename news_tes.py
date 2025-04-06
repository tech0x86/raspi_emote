import os
import requests

api_key = os.getenv('NEWS_API_KEY')

if not api_key:
    print("❌ APIキーが見つかんないよぉ…環境変数 'NEWS_API_KEY' を確認してね！")
    exit()

url = 'https://newsapi.org/v2/everything'
params = {
    'q': 'ETC',
    'language': 'ja',
    'sortBy': 'publishedAt',
    'apiKey': api_key
}

response = requests.get(url, params=params)

if response.status_code == 200:
    data = response.json()
    print('✅ ETCのニュースをゲットしたよ！')
    for i, article in enumerate(data.get('articles', [])[:5], 1):
        print(f"{i}. {article['title']}")
else:
    print('❌ ニュース取得に失敗しちゃった…ステータスコード:', response.status_code)
    print(response.text)
