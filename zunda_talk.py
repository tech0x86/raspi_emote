import time
import board
import pwmio
import RPi.GPIO as GPIO
import sys
import os
import random
import datetime
import threading
import queue
import json
import requests
from pathlib import Path
from voicevox_core import VoicevoxCore

# GPIOピンの設定
# PWM出力用に設定
red_pin = pwmio.PWMOut(board.D16, frequency=1000, duty_cycle=0)
green_pin = pwmio.PWMOut(board.D20, frequency=1000, duty_cycle=0)
blue_pin = pwmio.PWMOut(board.D21, frequency=1000, duty_cycle=0)

# 超音波センサーの設定
trig_pin = 15  # GPIO 15
echo_pin = 14  # GPIO 14
speed_of_sound = 34370  # 20℃での音速(cm/s)

GPIO.setmode(GPIO.BCM)  # GPIOをBCMモードで使用
GPIO.setwarnings(False)  # GPIO警告無効化
GPIO.setup(trig_pin, GPIO.OUT)  # Trigピン出力モード設定
GPIO.setup(echo_pin, GPIO.IN)  # Echoピン入力モード設定

# VOICEVOX Core設定
VOICEVOX_DICT_PATH = "./open_jtalk_dic_utf_8-1.11"
SPEAKER_ID = 1  # 1:ずんだもん, 2:四国めたん
AUDIO_CACHE_DIR = "./audio_cache"

# NewsAPI設定
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "あなたのAPIキーをここに設定")
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"

# グローバル変数
core = None  # VOICEVOXインスタンス
audio_queue = queue.Queue()  # 音声再生キュー
news_data = []  # ニュースデータ保存用
last_news_update = datetime.datetime.now() - datetime.timedelta(days=1)  # 前回ニュース更新時間
last_interaction_time = 0  # 最後の対話時間
emotion_state = "normal"  # 感情状態（normal, happy, angry, sad, surprised）

# ディレクトリ作成
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)

# LEDの明るさを設定する関数
def set_led_color(r, g, b):
    """LEDの色を設定します。
    Args:
        r (int): 赤色の明るさ (0～65535)。
        g (int): 緑色の明るさ (0～65535)。
        b (int): 青色の明るさ (0～65535)。
    """
    red_pin.duty_cycle = r
    green_pin.duty_cycle = g
    blue_pin.duty_cycle = b

# 超音波センサーで距離を取得する関数
def get_distance():
    GPIO.output(trig_pin, GPIO.HIGH)
    time.sleep(0.000010)
    GPIO.output(trig_pin, GPIO.LOW)

    while not GPIO.input(echo_pin):
        pass
    t1 = time.time()

    while GPIO.input(echo_pin):
        pass
    t2 = time.time()

    return (t2 - t1) * speed_of_sound / 2

# 感情に合わせたLEDセット
def set_emotion_led(emotion):
    global emotion_state
    emotion_state = emotion
    
    if emotion == "normal":
        set_led_color(32767, 32767, 32767)  # 白色
    elif emotion == "happy":
        set_led_color(0, 65535, 0)  # 緑色
    elif emotion == "angry":
        set_led_color(65535, 0, 0)  # 赤色
    elif emotion == "sad":
        set_led_color(0, 0, 65535)  # 青色
    elif emotion == "surprised":
        set_led_color(65535, 65535, 0)  # 黄色

# VOICEVOXで音声生成
def generate_voice(text):
    """VOICEVOXを使用して音声を生成し、ファイルパスを返します。"""
    global core
    
    # キャッシュファイル名を作成（テキストのハッシュ値を使用）
    text_hash = str(hash(text))
    cache_filename = os.path.join(AUDIO_CACHE_DIR, f"{text_hash}.wav")
    
    # キャッシュが存在すれば、それを返す
    if os.path.exists(cache_filename):
        return cache_filename
    
    try:
        # VOICEVOXインスタンスが初期化されていない場合は初期化
        if core is None:
            core = VoicevoxCore(open_jtalk_dict_dir=Path(VOICEVOX_DICT_PATH))
        
        # モデルが読み込まれていない場合は読み込む
        if not core.is_model_loaded(SPEAKER_ID):
            core.load_model(SPEAKER_ID)
        
        # 音声合成
        wave_bytes = core.tts(text, SPEAKER_ID)
        
        # 音声ファイル保存
        with open(cache_filename, "wb") as f:
            f.write(wave_bytes)
            
        return cache_filename
    
    except Exception as e:
        print(f"音声生成エラー: {e}")
        return None

# 音声再生関数
def play_audio(audio_file):
    """音声ファイルを再生します。"""
    try:
        # aplayコマンドを使用して音声を再生
        os.system(f"aplay {audio_file}")
    except Exception as e:
        print(f"音声再生エラー: {e}")

# 音声再生スレッド
def audio_player_thread():
    while True:
        audio_file = audio_queue.get()
        if audio_file is None:
            continue
        
        try:
            # 音声再生
            print(f"再生中: {audio_file}")
            play_audio(audio_file)
                
        except Exception as e:
            print(f"音声再生エラー: {e}")
        
        finally:
            audio_queue.task_done()

# 感情分析
def analyze_emotion(text):
    """テキストから感情を推測して、LEDの色を変更します。"""
    try:
        # 簡易的な感情分析（キーワードベース）
        if any(word in text for word in ["嬉しい", "楽しい", "やったー", "！！", "わーい"]):
            set_emotion_led("happy")
        elif any(word in text for word in ["怒", "むかっ", "許さない", "ひどい"]):
            set_emotion_led("angry")
        elif any(word in text for word in ["悲しい", "さみしい", "泣", "つらい"]):
            set_emotion_led("sad")
        elif any(word in text for word in ["びっくり", "えっ", "まさか", "驚"]):
            set_emotion_led("surprised")
        else:
            set_emotion_led("normal")
    except Exception as e:
        print(f"感情分析エラー: {e}")
        set_emotion_led("normal")

# ニュース取得
def fetch_news():
    """NewsAPIからニュースを取得します。"""
    global news_data, last_news_update
    
    try:
        params = {
            "country": "jp",
            "apiKey": NEWS_API_KEY,
            "pageSize": 10
        }
        
        response = requests.get(NEWS_API_URL, params=params)
        response.raise_for_status()
        result = response.json()
        
        if result["status"] == "ok" and result["articles"]:
            news_data = result["articles"]
            last_news_update = datetime.datetime.now()
            print(f"ニュース更新: {len(news_data)}件取得")
            return True
        
    except Exception as e:
        print(f"ニュース取得エラー: {e}")
    
    return False

# ランダムニュースの話題提供
def get_random_news_topic():
    """取得したニュースからランダムに一つ選び、トピックとして返します。"""
    global news_data
    
    # ニュースデータが空か1日以上経過していたら更新
    if not news_data or (datetime.datetime.now() - last_news_update).days >= 1:
        fetch_news()
    
    if news_data:
        article = random.choice(news_data)
        title = article.get("title", "")
        return f"最近のニュースで「{title}」というのがあるのだ。これについてどう思うのだ？"
    
    return "最近面白いニュースはあるのかな？"

# アイドル時の話題提供
def get_idle_topic():
    """アイドル状態（人がいない時）の話題をランダムに提供します。"""
    topics = [
        "今日の天気はどうかな？",
        "何か面白いことがあったのだ？",
        "ボクはずんだもちが大好きなのだ！",
        "プログラミング楽しいのだ！",
        "何か質問があれば言ってほしいのだ",
    ]
    
    return random.choice(topics)

# ランダム質問生成
def generate_random_question():
    """ランダムな質問を生成します。"""
    questions = [
        "あなたは何が好きなのだ？",
        "今日はどんな日だったのだ？",
        "何か面白いことがあったのかな？",
        "好きな食べ物は何なのだ？",
        "ボクのこと、どう思うのだ？"
    ]
    return random.choice(questions)

# 人が接近したときの挨拶
def greeting_on_approach():
    """人が接近したときに使用する挨拶文をランダムに返します。"""
    greetings = [
        "こんにちはなのだ！ボクはずんだもんなのだ！",
        "わーい！お客さんが来たのだ！",
        "いらっしゃいなのだ！何かお手伝いできることはあるのだ？",
        "こんにちはなのだ！今日はいい天気なのだ！",
        "ずんだもんだよ！よろしくなのだ！"
    ]
    return random.choice(greetings)

# 現在時刻表示
def display_current_time():
    """現在の日時を返します。"""
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"現在の時刻は{current_time}なのだ！"

# ずんだもんの応答を生成する関数（OpenAI代替版）
def generate_response(prompt):
    """ずんだもんの応答を生成します。"""
    # 実際のプロジェクトではOpenAI APIを使用するが、
    # このリファクタリングでは簡易版を実装
    responses = [
        f"うん、それは面白いのだ！{prompt}について考えてみたのだ",
        f"{prompt}? なるほどなのだ！ボクはずんだもんなのだ",
        f"ボクは{prompt}が好きなのだ！",
        f"{prompt}についてはよく分からないのだ…",
        f"わーい！{prompt}について話せて嬉しいのだ！"
    ]
    response = random.choice(responses)
    # 感情を分析して表現する
    analyze_emotion(response)
    return response

# メイン関数
def main():
    # 音声再生スレッドの開始
    audio_thread = threading.Thread(target=audio_player_thread, daemon=True)
    audio_thread.start()
    
    # 初回ニュース取得
    fetch_news()
    
    global last_interaction_time
    idle_counter = 0
    
    # 初期状態設定
    set_emotion_led("normal")
    
    print("ずんだもん対話システム起動完了！")
    
    try:
        while True:
            # 距離取得
            distance = get_distance()
            current_time = time.time()
            
            #print(f"距離: {distance:.1f} cm")
            
            # 人が近くにいる場合（1.5m以内）
            if distance < 150:
                # 前回の対話から30秒以上経過している場合
                if current_time - last_interaction_time > 30:
                    # 挨拶メッセージと時刻表示
                    greeting = greeting_on_approach()
                    time_info = display_current_time()
                    message = f"{greeting} {time_info}"
                    print(f"挨拶: {message}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(message)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    last_interaction_time = current_time
                    idle_counter = 0
                
                # 1m以内に近づいた場合はニュース提供
                elif distance < 100 and current_time - last_interaction_time > 15:
                    # ニュース話題
                    topic = get_random_news_topic()
                    print(f"ニュース: {topic}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(topic)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    last_interaction_time = current_time
                    idle_counter = 0
                
                # 0.5m以内に近づいた場合はより対話的な会話
                elif distance < 50 and current_time - last_interaction_time > 10:
                    # ランダムな話題と質問
                    question = generate_random_question()
                    print(f"質問: {question}")
                    
                    # 応答生成
                    response = generate_response(question)
                    print(f"応答: {response}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(response)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    last_interaction_time = current_time
                    idle_counter = 0
            
            # 人がいない場合のアイドル行動
            else:
                idle_counter += 1
                
                # 約10分ごとに独り言（600秒 ÷ 0.1秒のスリープ = 6000）
                if idle_counter >= 6000:
                    idle_topic = get_idle_topic()
                    print(f"独り言: {idle_topic}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(idle_topic)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    idle_counter = 0
            
            # 少し待機
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("プログラムを終了します。")
    
    finally:
        # 終了処理
        GPIO.cleanup()
        set_led_color(0, 0, 0)
        sys.exit()

if __name__ == "__main__":
    main()
