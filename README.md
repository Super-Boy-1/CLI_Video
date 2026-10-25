# ASCII 影片播放器

本專案提供一個簡易的 Python 腳本，可在終端機以 ASCII 字元播放 `video.mp4`，並使用 `pygame.mixer` 同步播放音訊。PyAV 會在 Python 程式內解碼 MP4 音軌，不需要另外安裝或呼叫 FFmpeg 命令列程式或 `ffplay`。

## 檔案結構
- **play_ascii.py** – 主程式。使用 OpenCV 讀取影格、轉換灰階並映射成 ASCII 字元；使用 PyAV 解碼影片音軌，再交由 `pygame.mixer` 播放。
- **requirements.txt** – Python 套件清單。
- **README.md** – 本說明文件。

## 前置條件
1. 已安裝 **Python 3.8+**。
2. 將名為 `video.mp4` 的影片放在 `play_ascii.py` 所在資料夾。
3. PyAV 需能解碼影片中的音訊編碼。程式會將音軌轉成暫存 WAV，再由 pygame 播放；播放結束後會刪除暫存檔。

## 安裝步驟
```bash
# （選擇性）建立並啟用虛擬環境
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
.\\venv\\Scripts\\activate.bat

# 安裝 Python 套件
pip install -r requirements.txt
```
套件清單包含 `opencv-python`（影片影格處理）、`av`（在 Python 程式內解碼影片音軌）、`pygame`（音訊播放）與 `Pillow`（執行快速的 Floyd–Steinberg 抖動）。

## 使用方法
```powershell
python play_ascii.py
python play_ascii.py --width 155
```
- `--width`：指定 ASCII 畫面寬度，預設為 160 個字元；可依終端機大小提高至 200。高度會依照影片比例及終端機字元長寬比（0.55）調整。

播放期間可按 **Ctrl+C** 中斷。程式結束時會停止音訊、釋放影片資源並恢復終端機游標。

## 工作原理簡述
1. OpenCV 開啟 `video.mp4`，並使用影片原生 FPS 排定每一幀的顯示時間。
2. 每一幀先轉成灰階並以線性對比調整（alpha 1.35、beta -18）加強明暗，再縮放並以 Floyd–Steinberg 誤差擴散抖動映射到字符集 ` .:-=+*#%@`。
3. 使用 Canny 偵測輪廓；輪廓區域依據 Sobel 梯度方向以 `/`、`\`、`|`、`-` 描繪，非輪廓區域則使用抖動後的亮度字符。處理後亮度不高於 40 的區域強制顯示空白，避免近黑背景被字符或輪廓線填滿。
4. 縮放時將終端字元長寬比係數設為 0.55，減少畫面垂直拉伸；使用 ANSI 控制碼更新畫面並於結束時恢復游標。
5. 程式使用 PyAV 解碼 MP4 音軌並暫存為 WAV，再由 `pygame.mixer.music` 播放。影片影格讀取完畢或使用者中斷時，程式會停止音訊並釋放資源。

## 影像處理參考
- [video-to-ascii 的影像處理程式](https://github.com/joelibaceta/video-to-ascii/blob/master/video_to_ascii/render_strategy/image_processor.py) 與 [ASCII-generator 的影像轉文字程式](https://github.com/vietnh1009/ASCII-generator/blob/master/img2txt.py) 提供了亮度轉字符的相關參考；目前採用的線稿覆蓋與 Floyd–Steinberg 抖動則由本程式自行整合。

## 授權協議
