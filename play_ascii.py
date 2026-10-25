#!/usr/bin/env python3
"""在終端機以 ASCII 字元播放影片，並使用 pygame 播放音訊。"""

import argparse
import math
import os
import sys
import tempfile
import time
import wave

import av
import cv2
import numpy as np
from PIL import Image

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(stdout_reconfigure):
    stdout_reconfigure(encoding="utf-8")

ASCII_CHARS = " .:-=+*#%@"
CHAR_ASPECT_RATIO = 0.55
EDGE_LOW_THRESHOLD = 70
EDGE_HIGH_THRESHOLD = 150
BLACK_LEVEL_THRESHOLD = 40
CONTRAST_ALPHA = 1.35
CONTRAST_BETA = -18


def floyd_steinberg_dither(gray):
    """使用 Floyd–Steinberg 誤差擴散，回傳每個像素對應的明暗字符索引。"""
    level_count = len(ASCII_CHARS)
    palette = []
    for index in range(level_count):
        value = round(index * 255 / (level_count - 1))
        palette.extend((value, value, value))
    palette.extend([255, 255, 255] * (256 - level_count))

    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette(palette)
    grayscale_image = Image.fromarray(gray).convert("RGB")
    quantized = grayscale_image.quantize(
        palette=palette_image,
        dither=Image.Dither.FLOYDSTEINBERG,
    )
    return np.asarray(quantized, dtype=np.uint8)


def extract_audio_to_wav(video_path):
    """使用 PyAV 解碼影片音軌，輸出 pygame 可載入的暫存 WAV 檔。"""
    temporary_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav_path = temporary_file.name
    temporary_file.close()
    succeeded = False

    try:
        sample_rate = 44100
        channels = 2
        resampler = av.AudioResampler(
            format="s16",
            layout="stereo",
            rate=sample_rate,
        )

        with av.open(video_path, mode="r") as container:
            if not container.streams.audio:
                raise RuntimeError(f"影片沒有音軌：{video_path}")

            with wave.open(wav_path, "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)

                audio_frame_count = 0
                # PyAV's stubs type av.open() as an input/output union, although mode="r" returns InputContainer.
                for packet in container.demux(audio=0):  # type: ignore[attr-defined]
                    for audio_frame in packet.decode():
                        for converted_frame in resampler.resample(audio_frame):
                            wav_file.writeframes(converted_frame.to_ndarray().tobytes())
                            audio_frame_count += 1

                for converted_frame in resampler.resample(None):
                    wav_file.writeframes(converted_frame.to_ndarray().tobytes())
                    audio_frame_count += 1

        if audio_frame_count == 0:
            raise RuntimeError(f"無法從影片解碼出音訊：{video_path}")

        succeeded = True
        return wav_path
    finally:
        if not succeeded and os.path.exists(wav_path):
            os.remove(wav_path)


def frame_to_ascii(frame, output_width):
    """以 Floyd–Steinberg 灰階字符和 Canny 線稿渲染單一影格。"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    contrasted = cv2.convertScaleAbs(
        gray,
        alpha=CONTRAST_ALPHA,
        beta=CONTRAST_BETA,
    )
    height, width = gray.shape
    output_height = max(
        1,
        int(height / width * output_width * CHAR_ASPECT_RATIO),
    )
    resized = cv2.resize(
        contrasted,
        (output_width, output_height),
        interpolation=cv2.INTER_AREA,
    )

    smoothed = cv2.GaussianBlur(resized, (3, 3), 0)
    edges = cv2.Canny(smoothed, EDGE_LOW_THRESHOLD, EDGE_HIGH_THRESHOLD)
    gradient_x = cv2.Sobel(smoothed, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(smoothed, cv2.CV_32F, 0, 1, ksize=3)
    tangent_angle = (
        np.degrees(np.arctan2(gradient_y, gradient_x)) + 90.0
    ) % 180.0

    indices = floyd_steinberg_dither(resized)
    character_grid = np.asarray(list(ASCII_CHARS))[indices]
    visible_pixels = resized > BLACK_LEVEL_THRESHOLD

    edge_characters = np.full(edges.shape, "-", dtype="<U1")
    edge_characters[(tangent_angle >= 22.5) & (tangent_angle < 67.5)] = "\\"
    edge_characters[(tangent_angle >= 67.5) & (tangent_angle < 112.5)] = "|"
    edge_characters[(tangent_angle >= 112.5) & (tangent_angle < 157.5)] = "/"
    edge_mask = (edges > 0) & visible_pixels
    character_grid[edge_mask] = edge_characters[edge_mask]
    character_grid[~visible_pixels] = ASCII_CHARS[0]

    lines = ["".join(row.tolist()) for row in character_grid]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="在終端機以 ASCII 字元播放影片，並同步播放音訊。"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=160,
        help="ASCII 畫面的寬度（預設：160）",
    )
    args = parser.parse_args()
    if args.width <= 0:
        parser.error("--width 必須是正整數")

    video_path = "video.mp4"
    if not os.path.isfile(video_path):
        parser.error(f"找不到影片檔案：{video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"OpenCV 無法開啟影片：{video_path}")

    cursor_hidden = False
    mixer_initialized = False
    audio_path = None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            raise RuntimeError("無法取得有效的影片 FPS。")

        ret, frame = cap.read()
        if not ret:
            raise RuntimeError("影片沒有可讀取的畫面。")

        # 預先轉換第一幀，讓音訊開始後能立即顯示畫面。
        ascii_frame = frame_to_ascii(frame, args.width)
        audio_path = extract_audio_to_wav(video_path)

        pygame.mixer.init()
        mixer_initialized = True
        pygame.mixer.music.load(audio_path)

        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        cursor_hidden = True

        # 先啟動音訊，再立即顯示已準備好的第一幀，讓兩者從同一播放起點開始。
        pygame.mixer.music.play()
        start_time = time.perf_counter()
        frame_index = 0

        while ret:
            frame_time = start_time + frame_index / fps
            remaining = frame_time - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)

            sys.stdout.write("\033[H" + ascii_frame + "\033[J")
            sys.stdout.flush()
            frame_index += 1

            ret, frame = cap.read()
            if ret:
                ascii_frame = frame_to_ascii(frame, args.width)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if mixer_initialized:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        if cursor_hidden:
            sys.stdout.write("\033[?25h\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
