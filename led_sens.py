import time
import board
import pwmio
import RPi.GPIO as GPIO
import sys

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

# 虹色のグラデーションを表示する関数
def rainbow(wait_ms=10, iterations=1):
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

# 虹色の色を生成する関数
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
        distance = get_distance()
        print(f"Distance: {distance:.1f} cm")

        if distance < 100:  # 100cm以内に物体を検知
            # 距離に応じて点滅速度を調整
            blink_speed = max(0.1, distance / 100)  # 最小0.1秒
            set_led_color(65535, 0, 0)  # 赤色点灯
            time.sleep(blink_speed)
            set_led_color(0, 0, 0)  # 消灯
            time.sleep(blink_speed)
        else:
            # 虹色のグラデーションを表示
            rainbow(wait_ms=10, iterations=1)

except KeyboardInterrupt:
    # Ctrl+Cが押されたらGPIOとLEDを片付け
    GPIO.cleanup()
    set_led_color(0, 0, 0)
    sys.exit()