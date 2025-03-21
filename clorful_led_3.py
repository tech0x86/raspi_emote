import time
import board
import pwmio
import digitalio

# GPIOピンの設定
# PWM出力用に設定
red_pin = pwmio.PWMOut(board.D16, frequency=1000, duty_cycle=0)
green_pin = pwmio.PWMOut(board.D20, frequency=1000, duty_cycle=0)
blue_pin = pwmio.PWMOut(board.D21, frequency=1000, duty_cycle=0)

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

def color_wipe(r, g, b, wait_ms=50):
    """LEDを特定の色で順番に点灯させる関数。

    Args:
        r (int): 赤色の明るさ (0～65535)。
        g (int): 緑色の明るさ (0～65535)。
        b (int): 青色の明るさ (0～65535)。
        wait_ms (int): 点灯間の待ち時間 (ミリ秒)。
    """
    set_led_color(r, g, b)
    time.sleep(wait_ms / 1000.0)

def rainbow(wait_ms=10, iterations=5): # 繰り返しの回数を増やしました
    """虹色のグラデーションを表示する関数。

    Args:
        wait_ms (int): 色が変わる間の待ち時間 (ミリ秒)。
        iterations (int): 繰り返しの回数。
    """
    for j in range(256 * iterations):
        for i in range(1):  # 複数のLEDがある場合を考慮したループ
            pixel_index = (i * 256 // 1) + j
            r, g, b = wheel(pixel_index & 255)
            set_led_color(r, g, b)
        time.sleep(wait_ms / 1000.0)

def wheel(pos):
    """虹色のグラデーションを生成する関数。

    Args:
        pos (int): 色の位置 (0～255)。

    Returns:
        tuple: (r, g, b) のタプル。各色は0～65535の範囲の値。
    """
    if pos < 85:
        return (int(pos * 3 * 257), int((255 - pos * 3) * 257), 0)
    elif pos < 170:
        pos -= 85
        return (int((255 - pos * 3) * 257), 0, int(pos * 3 * 257))
    else:
        pos -= 170
        return 0, int(pos * 3 * 257), int((255 - pos * 3) * 257)

# メインループ
try:
    while True:
        # 赤、緑、青の順番で点灯（明るさ調整版）
        color_wipe(65535, 0, 0)  # 赤
        color_wipe(0, 30000, 0)  # 緑
        color_wipe(0, 0, 65535)  # 青
        # 虹色のグラデーション
        rainbow()
except KeyboardInterrupt:
    # Ctrl+Cが押されたらLEDを消灯
    set_led_color(0, 0, 0)
