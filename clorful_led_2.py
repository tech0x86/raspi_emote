import time
import board
import digitalio

# GPIOピンの設定
red_pin = digitalio.DigitalInOut(board.D16)
green_pin = digitalio.DigitalInOut(board.D20)
blue_pin = digitalio.DigitalInOut(board.D21)

# ピンの方向を出力に設定
red_pin.direction = digitalio.Direction.OUTPUT
green_pin.direction = digitalio.Direction.OUTPUT
blue_pin.direction = digitalio.Direction.OUTPUT

# LEDの光度 (0.0 から 1.0)
brightness = 0.2  # この例では直接的な明るさ調整は難しい

# LEDの点灯/消灯を制御する関数
def set_led_color(r_on, g_on, b_on):
    """LEDの色を設定します。

    Args:
        r_on (bool): 赤色LEDを点灯させる場合はTrue、消灯させる場合はFalse。
        g_on (bool): 緑色LEDを点灯させる場合はTrue、消灯させる場合はFalse。
        b_on (bool): 青色LEDを点灯させる場合はTrue、消灯させる場合はFalse。
    """
    red_pin.value = r_on
    green_pin.value = g_on
    blue_pin.value = b_on

def color_wipe(r, g, b, wait_ms=50):
    """LEDを特定の色で順番に点灯させる関数。

    Args:
        r (int): 赤色の値 (0 または 1)。
        g (int): 緑色の値 (0 または 1)。
        b (int): 青色の値 (0 または 1)。
        wait_ms (int): 点灯間の待ち時間 (ミリ秒)。
    """
    set_led_color(r, g, b)
    time.sleep(wait_ms / 1000.0)

def rainbow(wait_ms=20, iterations=1):
    """虹色のグラデーションを表示する関数。
    Args:
        wait_ms (int): 色が変わる間の待ち時間 (ミリ秒)。
        iterations (int): 繰り返しの回数。
    """
    for j in range(256 * iterations):
        r, g, b = wheel(j & 255) # wheel関数はそのまま使用可能
        set_led_color(r, g, b)
        time.sleep(wait_ms / 1000.0)

def wheel(pos):
    """虹色のグラデーションを生成する関数。
    Args:
        pos (int): 色の位置 (0～255)。
    Returns:
        tuple: (r, g, b) のタプル。各色は0または1。
    """
    if pos < 85:
        return (1, 0, 0) if pos * 3 > 0 else (0,0,0), (0, 1, 0) if 255 - pos * 3 > 0 else (0,0,0), 0
    elif pos < 170:
        pos -= 85
        return (0, 1, 0) if 255 - pos * 3 > 0 else (0,0,0), 0, (0, 0, 1) if pos * 3 > 0 else (0,0,0)
    else:
        pos -= 170
        return 0, (0, 0, 1) if pos * 3 > 0 else (0,0,0), (1, 0, 0) if 255 - pos * 3 > 0 else (0,0,0)

# メインループ
try:
    while True:
        # 赤、緑、青の順番で点灯
        color_wipe(1, 0, 0)  # 赤
        color_wipe(0, 1, 0)  # 緑
        color_wipe(0, 0, 1)  # 青
        # 虹色のグラデーション
        rainbow()
except KeyboardInterrupt:
    # Ctrl+Cが押されたらLEDを消灯
    set_led_color(0, 0, 0)
