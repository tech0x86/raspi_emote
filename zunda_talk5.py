# 初期化部分にVOICEVOXのimport追加（ファイル先頭部分）
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
import tkinter as tk
from tkinter import ttk, scrolledtext
from PIL import Image, ImageTk
import threading
import pandas as pd

# VOICEVOXのインポートを追加
try:
    from voicevox_core import VoicevoxCore
except ImportError:
    add_log("VOICEVOXモジュールがインストールされていません。音声合成は無効です。")
    VoicevoxCore = None

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
USE_VOICEBOX_ONLY_FOR_NEWS = True  # ニュースのみVOICEBOXを使用

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
current_distance = 0  # 現在の距離
log_messages = []  # ログメッセージ保存用
log_max_lines = 10  # ログの最大行数

# GUIのグローバル参照
gui_root = None
distance_label = None
time_label = None
log_text = None
character_label = None

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

# ログ追加関数
def add_log(message):
    """ログにメッセージを追加し、GUIのログ表示を更新します。"""
    global log_messages
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    
    # ターミナルにも出力
    print(log_message)
    
    # ログリストに追加
    log_messages.append(log_message)
    
    # 最大行数を超えた場合、古いものを削除
    if len(log_messages) > log_max_lines:
        log_messages = log_messages[-log_max_lines:]
    
    # GUIのログ表示を更新
    if log_text:
        gui_root.after(10, update_log_text)

# ログテキスト更新
def update_log_text():
    """GUI上のログテキストを更新します。"""
    if log_text:
        log_text.config(state=tk.NORMAL)
        log_text.delete(1.0, tk.END)
        for msg in log_messages:
            log_text.insert(tk.END, msg + "\n")
        log_text.config(state=tk.DISABLED)
        log_text.see(tk.END)  # 自動スクロール
# 音声生成関数の修正（generate_voice関数）
def generate_voice(text, force_generate=False):
    """VOICEVOXを使用して音声を生成し、ファイルパスを返します。"""
    global core
    
    # キャッシュファイル名を作成（テキストのハッシュ値を使用）
    text_hash = str(abs(hash(text)))  # 絶対値を取り、ハイフンを避ける
    cache_filename = os.path.join(AUDIO_CACHE_DIR, f"{text_hash}.wav")
    
    # キャッシュが存在すれば、それを返す
    if os.path.exists(cache_filename):
        add_log(f"キャッシュ使用: {text[:20]}...")
        return cache_filename
    
    try:
        # VOICEVOXインスタンスが初期化されていない場合は初期化
        if core is None:
            from voicevox_core import VoicevoxCore
            from pathlib import Path
            add_log("VOICEVOX Coreを初期化中...")
            core = VoicevoxCore(open_jtalk_dict_dir=Path(VOICEVOX_DICT_PATH))
        
        # モデルがロードされているか確認し、必要ならロード
        if not core.is_model_loaded(SPEAKER_ID):
            add_log(f"VOICEVOX モデル {SPEAKER_ID} をロード中...")
            core.load_model(SPEAKER_ID)
        
        # 音声合成を実行
        add_log("音声生成中...")
        wave_bytes = core.tts(text, SPEAKER_ID)
        
        # ファイルに保存
        with open(cache_filename, "wb") as f:
            f.write(wave_bytes)
            
        add_log(f"音声生成完了: {text[:20]}...")
        return cache_filename
    
    except Exception as e:
        add_log(f"音声生成エラー: {e}")
        # エラーが発生した場合、簡易的なダミーファイルを作成（テスト用）
        try:
            with open(cache_filename, "wb") as f:
                # テスト用の空ファイル
                f.write(b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00')
            add_log(f"ダミー音声ファイル作成: {text[:20]}...")
            return cache_filename
        except:
            return None
        
# VOICEVOX関連のエラーハンドリングを追加（音声再生関数）
def play_audio(audio_file):
    """音声ファイルを再生します。"""
    try:
        if not os.path.exists(audio_file):
            add_log(f"音声ファイルが見つかりません: {audio_file}")
            return
            
        # ファイルサイズチェック
        if os.path.getsize(audio_file) < 100:  # 極端に小さいファイルはスキップ
            add_log(f"無効な音声ファイルをスキップします: {audio_file}")
            return
            
        # aplayコマンドを使用して音声を再生
        add_log(f"音声再生: {os.path.basename(audio_file)}")
        os.system(f"aplay {audio_file}")
    except Exception as e:
        add_log(f"音声再生エラー: {e}")

# 音声再生スレッド
def audio_player_thread():
    while True:
        audio_file = audio_queue.get()
        if audio_file is None:
            continue
        
        try:
            # 音声再生
            add_log(f"再生中: {os.path.basename(audio_file)}")
            play_audio(audio_file)
                
        except Exception as e:
            add_log(f"音声再生エラー: {e}")
        
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
        add_log(f"感情分析エラー: {e}")
        set_emotion_led("normal")

# NewsAPIのクエリを修正（fetch_news関数）
def fetch_news():
    """NewsAPIからニュースを取得します。"""
    global news_data, last_news_update
    
    try:
        # NewsAPI URLとパラメータの設定
        url = "https://newsapi.org/v2/top-headlines"
        
        # 指定したキーワード（速報、IT、AI、農業）を含む記事を検索
        params = {
            "country": "jp",
            "q": "速報 OR IT OR AI OR 農業",  # キーワードの指定（OR検索）
            "pageSize": 10
        }
        
        # ヘッダーの設定
        headers = {
            "X-Api-Key": NEWS_API_KEY
        }
        
        add_log("ニュース取得中...")
        
        # リクエスト送信
        response = requests.get(url, headers=headers, params=params)
        
        # レスポンスの確認
        if response.ok:
            data = response.json()
            
            # データフレームの作成
            import pandas as pd
            df = pd.DataFrame(data['articles'])
            
            # 総結果数をログに記録
            add_log(f"ニュース: 総結果数 {data['totalResults']}")
            
            # データフレームの特定の列を表示
            column_data = df[['publishedAt', 'title', 'url']]
            add_log(f"取得したニュース: {len(column_data)}件")
            
            # ニュースデータを保存
            news_data = data['articles']
            last_news_update = datetime.datetime.now()
            
            # デバッグ用：最初の3件のニュースタイトルをログに記録
            for i, row in column_data.head(3).iterrows():
                add_log(f"ニュース{i+1}: {row['title']}")
            
            return True
        else:
            add_log(f"ニュース取得エラー: ステータスコード {response.status_code}")
            return False
        
    except Exception as e:
        add_log(f"ニュース取得エラー: {e}")
        return False

# ランダムニュースの話題提供関数の修正
def get_random_news_topic():
    """取得したニュースからランダムに一つ選び、トピックとして返します。"""
    global news_data
    
    # ニュースデータが空か1日以上経過していたら更新
    if not news_data or (datetime.datetime.now() - last_news_update).days >= 1:
        success = fetch_news()
        if not success:
            return "ニュースの取得に失敗したのだ。ごめんなさいなのだ。"
    
    if news_data:
        article = random.choice(news_data)
        title = article.get("title", "")
        
        # タイトルが短すぎる場合はエラーメッセージ
        if len(title) <= 5:
            add_log(f"ニュース: タイトルが短すぎます ({title})")
            return "ニュースのタイトルが不適切なのだ。別のニュースを探すのだ。"
            
        # ログにニュースタイトルを表示
        add_log(f"選択したニュース: {title}")
        return f"最近のニュースで「{title}」というのがあるのだ。これについてどう思うのだ？"
    
    return "最近のニュース情報がないのだ。また後で試してみるのだ。"

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

# 時刻表示関数の更新（update_gui関数内）
def update_gui():
    """GUIを更新する関数"""
    global current_distance
    
    # 現在時刻を更新
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M")  # 時:分
    date_str = now.strftime("%Y-%m-%d")  # 年-月-日
    
    if time_label:
        # HTML形式で時刻部分を大きくする
        time_label.config(
            text=f"現在時刻: {date_str} ",
            font=("Helvetica", 18),
            compound=tk.LEFT
        )
        
        # 時刻を別ラベルで大きく表示
        if not hasattr(time_label, 'time_only_label'):
            time_label.time_only_label = tk.Label(
                time_label.master,
                font=("Helvetica", 200 ),
                fg="#000000"
            )
            time_label.time_only_label.pack(side=tk.LEFT, padx=0)
        
        time_label.time_only_label.config(text=time_str)
    
    # 距離を更新
    if distance_label:
        distance_label.config(text=f"距離: {current_distance:.1f} cm")
    
    # 次の更新をスケジュール
    if gui_root:
        gui_root.after(1000, update_gui)

# GUIを作成する関数
def create_gui():
    """GUIウィンドウを作成します。"""
    global gui_root, distance_label, time_label, log_text, character_label
    
    # ウィンドウ作成
    gui_root = tk.Tk()
    gui_root.title("ずんだもん対話システム")
    gui_root.geometry("1080x1920")
    
    # フルスクリーン設定
    gui_root.attributes('-fullscreen', True)
    
    # フレームを作成
    top_frame = tk.Frame(gui_root)
    top_frame.pack(fill=tk.X, padx=10, pady=10)
    
    # 現在時刻ラベル
    time_label = tk.Label(top_frame, text="現在時刻: -", font=("Helvetica", 72))
    time_label.pack(side=tk.LEFT, padx=5)
    
    # 距離ラベル
    distance_label = tk.Label(top_frame, text="距離: - cm", font=("Helvetica", 14))
    distance_label.pack(side=tk.RIGHT, padx=5)
    
    # キャラクター表示領域
    character_frame = tk.Frame(gui_root, bg="#F0F0F0", height=300)
    character_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    # ずんだもん画像の読み込みと表示
    try:
        zundamon_image = Image.open("./pic_zunda/zunda_normal.png")

        # フレームサイズを取得
        character_frame.update_idletasks()
        frame_width = character_frame.winfo_width()
        frame_height = character_frame.winfo_height()
        
        # 画像のサイズ取得と縦横比の計算
        img_width, img_height = zundamon_image.size
        aspect_ratio = img_width / img_height
        
        # 最低限のサイズを設定（小さい解像度の場合は引き伸ばす）
        min_width = max(int(frame_width * 0.6), img_width)  # intに変換
        min_height = max(int(frame_height * 0.6), img_height)  # intに変換
        
        # アスペクト比を維持しながら、必要なサイズまで引き伸ばす
        if min_width / min_height > aspect_ratio:
            # 高さを基準に幅を計算
            new_height = min_height
            new_width = int(new_height * aspect_ratio)
        else:
            # 幅を基準に高さを計算
            new_width = min_width
            new_height = int(new_width / aspect_ratio)
        
        # フレームに収める（大きすぎる場合は縮小）
        if new_width > frame_width:
            new_width = int(frame_width)  # intに明示的に変換
            new_height = int(new_width / aspect_ratio)
        
        if new_height > frame_height:
            new_height = int(frame_height)  # intに明示的に変換
            new_width = int(new_height * aspect_ratio)
        
        # リサイズ
        zundamon_image = zundamon_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        zundamon_photo = ImageTk.PhotoImage(zundamon_image)
        character_label = tk.Label(character_frame, image=zundamon_photo, bg="#F0F0F0")
        character_label.image = zundamon_photo  # 参照を保持
        character_label.pack(expand=True)
    except Exception as e:
        # 画像が読み込めない場合はテキスト表示にフォールバック
        add_log(f"画像読み込みエラー: {e}")
        character_label = tk.Label(character_frame, text="ずんだもん", font=("Helvetica", 40))
        character_label.pack(expand=True)
    
    
        
    # ログ表示領域
    log_frame = tk.LabelFrame(gui_root, text="ログ", height=150)
    log_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
    
    # スクロール可能なテキストエリア
    log_text = scrolledtext.ScrolledText(log_frame, height=8)
    log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    log_text.config(state=tk.DISABLED)
    
    # GUI更新開始
    update_gui()
    
    return gui_root

# GUIスレッド
def run_gui():
    """GUIスレッドを実行します。"""
    gui = create_gui()
    gui.mainloop()

def main():
    # GUIスレッドの開始
    gui_thread_instance = threading.Thread(target=run_gui, daemon=True)
    gui_thread_instance.start()
    
    # 音声再生スレッドの開始
    audio_thread = threading.Thread(target=audio_player_thread, daemon=True)
    audio_thread.start()
    
    # VOICEVOXの初期化確認
    global core
    try:
        if VoicevoxCore is not None:
            from pathlib import Path
            add_log("VOICEVOX Coreを初期化中...")
            core = VoicevoxCore(open_jtalk_dict_dir=Path(VOICEVOX_DICT_PATH))
            if core.is_model_loaded(SPEAKER_ID):
                add_log(f"VOICEVOX モデル {SPEAKER_ID} はすでにロードされています")
            else:
                add_log(f"VOICEVOX モデル {SPEAKER_ID} をロード中...")
                core.load_model(SPEAKER_ID)
            add_log("VOICEVOX Core 初期化完了")
    except Exception as e:
        add_log(f"VOICEVOX初期化エラー: {e}")
        core = None
    
    # 初回ニュース取得
    fetch_news()
    
    global last_interaction_time, current_distance
    idle_counter = 0
    
    # 初期状態設定
    set_emotion_led("normal")
    
    add_log("ずんだもん対話システム起動完了！")
    
    try:
        while True:
            # 距離取得
            current_distance = get_distance()
            current_time = time.time()
            
            # 人が近くにいる場合（1.5m以内）
            if current_distance < 150:
                # 前回の対話から30秒以上経過している場合
                if current_time - last_interaction_time > 30:
                    # 挨拶メッセージと時刻表示
                    greeting = greeting_on_approach()
                    message = f"{greeting}"
                    add_log(f"挨拶: {message}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(message)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    last_interaction_time = current_time
                    idle_counter = 0
                
                # 1m以内に近づいた場合はニュース提供
                elif current_distance < 100 and current_time - last_interaction_time > 15:
                    # ニュース話題
                    topic = get_random_news_topic()
                    add_log(f"ニュース提供: {topic}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(topic)
                    if audio_file:
                        audio_queue.put(audio_file)
                    else:
                        add_log("ニュース音声の生成に失敗しました")
                    
                    last_interaction_time = current_time
                    idle_counter = 0
                
                # 0.5m以内に近づいた場合はより対話的な会話
                elif current_distance < 50 and current_time - last_interaction_time > 10:
                    # ランダムな話題と質問
                    question = generate_random_question()
                    add_log(f"質問: {question}")
                    
                    # 応答生成
                    response = generate_response(question)
                    add_log(f"応答: {response}")
                    
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
                    add_log(f"独り言: {idle_topic}")
                    
                    # 音声生成と再生
                    audio_file = generate_voice(idle_topic)
                    if audio_file:
                        audio_queue.put(audio_file)
                    
                    idle_counter = 0
            
            # 少し待機
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        add_log("プログラムを終了します。")
    
    finally:
        # 終了処理
        GPIO.cleanup()
        set_led_color(0, 0, 0)
        sys.exit()
        
if __name__ == "__main__":
    main()
