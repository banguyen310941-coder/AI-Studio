# AI Studio 3.0

Ứng dụng dựng video desktop bằng PySide6 và FFmpeg.

## Chức năng

- Tạo video AI theo dự án/kịch bản hiện có.
- **Ảnh thành video:** nhập nhiều ảnh, tự tạo chuyển động Ken Burns, chọn video ngang/dọc/vuông, ghép nhạc nền và xuất MP4.
- **AI Video Editor:** nhập video đã quay, cắt đầu/cuối, thay đổi tốc độ, chuyển khung hình TikTok/YouTube/vuông, tắt tiếng gốc, ghép nhạc và đốt phụ đề SRT/ASS/VTT.
- Phân tích một số yêu cầu chỉnh sửa tiếng Việt như: “cắt 3 giây đầu, tăng tốc 1.25x, chuyển thành video dọc TikTok, tắt tiếng gốc”.

## Cài đặt trên macOS

```bash
cd "AI Studio"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg
python main.py
```

Để đốt phụ đề trực tiếp lên video, FFmpeg cần filter `subtitles` (libass). Kiểm tra:

```bash
ffmpeg -hide_banner -filters | grep subtitles
```

Nếu bản FFmpeg hiện tại không có filter này, cài bản hỗ trợ libass hoặc dùng chức năng không đốt phụ đề.

## Bảo mật

File `.env` không nằm trong gói bàn giao. Tạo `.env` riêng trên máy và không chia sẻ API key.

## AI Film Studio 4.0

Menu **AI Film Studio** bổ sung quy trình:

1. Nhập ý tưởng phim và thời lượng tối thiểu 15 phút.
2. Tự động chia thành các shot 8 giây, cấu trúc 3 hồi và tạo prompt tiếng Anh cho Veo.
3. Render tuần tự bằng Gemini API/Veo, tự lưu trạng thái sau từng shot để có thể tiếp tục.
4. Có thể gắn clip thủ công nếu một shot được tạo ngoài phần mềm.
5. Ghép các clip hoàn thành bằng FFmpeg và xuất `final_film.mp4`.

Cấu hình khóa trong `.env`:

```bash
GEMINI_API_KEY=...
```

Phim 15 phút cần khoảng 113 clip 8 giây. Render toàn bộ có thể mất nhiều giờ và phát sinh chi phí API. Hãy thử trước với một số shot hoặc dùng mô hình Fast.
