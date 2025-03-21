import time
import board
import neopixel

# LEDの数
num_pixels = 1

# GPIOピンの設定
pixel_pin = board.D16  # 赤
pixel_pin_g = board.D20  # 緑
pixel_pin_b = board.D21  # 青

# LEDの明るさ (0.0 から 1.0)
brightness = 0.2

# LEDの光度 (mcd)
led_intensity_r = 2000
led_intensity_g = 7000
led_intensity_b = 2500

# 光度比率の計算
max_intensity = max(led_intensity_r, led_intensity_g, led_intensity_b)
intensity_ratio_r = led_intensity_r / max_intensity
intensity_ratio_g = led_intensity_g / max_intensity
intensity_ratio_b = led_intensity_b / max_intensity

# 調整後の明るさ係数
adjusted_brightness_r = brightness / intensity_ratio_r
adjusted_brightness_g = brightness / intensity_ratio_g
adjusted_brightness_b = brightness / intensity_ratio_b
# LEDの初期化
pixels_r = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=adjusted_brightness_r, auto_write=False)
pixels_g = neopixel.NeoPixel(pixel_pin_g, num_pixels, brightness=adjusted_brightness_g, auto_write=False)
pixels_b = neopixel.NeoPixel(pixel_pin_b, num_pixels, brightness=adjusted_brightness_b, auto_write=False)

def color_wipe(r, g, b, wait_ms=50):
    """LEDを特定の色で順番に点灯させる"""
    for i in range(num_pixels):
        pixels_r[i] = (r, 0, 0)
        pixels_g[i] = (0, g, 0)
        pixels_b[i] = (0, 0, b)
        pixels_r.show()
        pixels_g.show()
        pixels_b.show()
        time.sleep(wait_ms / 1000.0)

def rainbow(wait_ms=20, iterations=1):
    """虹色のグラデーションを表示する"""
    for j in range(256 * iterations):
        for i in range(num_pixels):
            pixel_index = (i * 256 // num_pixels) + j
            r, g, b = wheel(pixel_index & 255)
            pixels_r[i] = (r, 0, 0)
            pixels_g[i] = (0, g, 0)
            pixels_b[i] = (0, 0, b)
        pixels_r.show()
        pixels_g.show()
        pixels_b.show()
        time.sleep(wait_ms / 1000.0)

def wheel(pos):
    """虹色のグラデーションを生成する"""
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

# メインループ
try:
    while True:
        # 赤、緑、青の順番で点灯
        color_wipe(255, 0, 0)  # 赤
        color_wipe(0, 255, 0)  # 緑
        color_wipe(0, 0, 255)  # 青
        # 虹色のグラデーション
        rainbow()
except KeyboardInterrupt:
    # Ctrl+Cが押されたらLEDを消灯
    pixels_r.fill((0, 0, 0))
    pixels_g.fill((0, 0, 0))
    pixels_b.fill((0, 0, 0))
    pixels_r.show()
    pixels_g.show()
    pixels_b.show()
