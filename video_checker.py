import cv2
import os
import numpy as np
import re
from pathlib import Path
from typing import List, Tuple

def check_video_motion(video_path, threshold=500, time_box=(0, 0, 150, 40), ratio_threshold=0.1):
    """
    检查视频是否有画面变动，忽略时间戳区域
    
    Args:
        video_path: 视频文件路径
        threshold: 检测变动的阈值，数值越小越敏感
        time_box: 时间戳区域的坐标 (x1, y1, x2, y2)，这个区域会被忽略
        ratio_threshold: 变化像素占比阈值（百分比），超过这个比例才认为有变动
    
    Returns:
        bool: True表示有变动，False表示无变动
    """
    cap = cv2.VideoCapture(str(video_path))
    
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return True
    
    # 读取第一帧
    ret, prev_frame = cap.read()
    if not ret:
        cap.release()
        return True
    
    # 获取视频的总帧数和帧率
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = frame_count / fps
    print(f"\n处理视频: {os.path.basename(video_path)}")
    print(f"视频时长: {duration:.2f}秒, 总帧数: {frame_count}")
    
    # 将时间戳区域填充为黑色
    x1, y1, x2, y2 = time_box
    prev_frame[y1:y2, x1:x2] = 0
    
    # 转换为灰度图并进行高斯模糊以减少噪声
    prev_frame_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_frame_gray = cv2.GaussianBlur(prev_frame_gray, (21, 21), 0)
    
    check_interval = max(1, frame_count // 20)  # 每隔5%的帧数检查一次
    frame_idx = 0
    max_diff = 0
    max_ratio = 0
    total_checked_frames = 0
    
    # 计算总像素数（不包括时间戳区域）
    total_pixels = (prev_frame_gray.shape[0] * prev_frame_gray.shape[1]) - ((x2 - x1) * (y2 - y1))
    
    has_motion = False
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_idx += 1
        if frame_idx % check_interval != 0:
            continue
            
        total_checked_frames += 1
        
        # 将时间戳区域填充为黑色
        frame[y1:y2, x1:x2] = 0
        
        # 转换为灰度图并进行高斯模糊
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_gray = cv2.GaussianBlur(frame_gray, (21, 21), 0)
        
        # 计算帧差
        diff = cv2.absdiff(frame_gray, prev_frame_gray)
        
        # 对差异图像进行二值化处理
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        
        # 进行形态学操作以去除小的噪点
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # 计算非零像素的数量作为变化量
        diff_count = np.count_nonzero(thresh)
        max_diff = max(max_diff, diff_count)
        
        # 计算变化比例
        diff_ratio = (diff_count / total_pixels) * 100
        max_ratio = max(max_ratio, diff_ratio)
        
        # 只有当像素变化数量大于阈值且变化比例大于比例阈值时，才认为有变动
        if diff_count > threshold and diff_ratio > ratio_threshold:
            print(f"第 {frame_idx} 帧检测到变动:")
            print(f"差异像素数: {diff_count}")
            print(f"差异比例: {diff_ratio:.2f}%")
            has_motion = True
            break
            
        prev_frame_gray = frame_gray
    
    cap.release()
    
    if not has_motion:
        print(f"未检测到明显变动")
        print(f"最大差异像素数: {max_diff}")
        print(f"最大差异比例: {max_ratio:.2f}%")
    print(f"检查了 {total_checked_frames} 帧")
    
    return has_motion

def parse_video_time(filename: str) -> Tuple[int, int]:
    """
    从文件名解析视频时间信息
    
    Args:
        filename: 文件名（格式如：04M21S_1723482261）
    
    Returns:
        Tuple[int, int]: (分钟, 秒)
    """
    match = re.match(r'(\d+)M(\d+)S_\d+', filename)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes, seconds
    return 0, 0

def get_video_duration(video_path: str) -> float:
    """
    获取视频时长（秒）
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps
    
    cap.release()
    return duration

def concatenate_videos(video_files: List[Path], output_path: str):
    """
    按时间顺序拼接视频文件，并使用高效的编码方式
    
    Args:
        video_files: 视频文件路径列表
        output_path: 输出视频路径
    """
    if not video_files:
        print("没有需要拼接的视频文件")
        return
    
    # 按时间排序视频文件
    sorted_videos = sorted(video_files, 
                         key=lambda x: parse_video_time(x.stem))
    
    # 获取第一个视频的属性
    first_video = cv2.VideoCapture(str(sorted_videos[0]))
    if not first_video.isOpened():
        print(f"无法打开视频: {sorted_videos[0]}")
        return
    
    frame_width = int(first_video.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(first_video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = first_video.get(cv2.CAP_PROP_FPS)
    first_video.release()
    
    # 使用 H.264 编码，设置较高的压缩率
    if os.path.exists(output_path):
        os.remove(output_path)  # 如果文件已存在，先删除
        
    fourcc = cv2.VideoWriter_fourcc(*'H264')
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
    
    if not out.isOpened():
        print("无法创建输出视频文件，尝试使用其他编码格式...")
        # 如果H264不可用，尝试使用mp4v
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
    
    # 拼接视频
    for video_path in sorted_videos:
        print(f"正在处理视频: {video_path}")
        cap = cv2.VideoCapture(str(video_path))
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
        
        cap.release()
    
    out.release()
    print(f"视频拼接完成，已保存至: {output_path}")
    
    # 如果系统支持，使用ffmpeg进行二次压缩
    try:
        temp_output = output_path + ".temp.mp4"
        os.rename(output_path, temp_output)
        os.system(f'ffmpeg -i "{temp_output}" -c:v libx264 -crf 23 "{output_path}"')
        os.remove(temp_output)
        print("视频已完成二次压缩")
    except Exception as e:
        print(f"二次压缩失败: {e}")

def process_video_folder(folder_path, threshold=500, concat=True, time_box=(0, 0, 150, 40), ratio_threshold=0.1):
    """
    处理文件夹中的所有视频文件
    
    Args:
        folder_path: 视频文件夹路径
        threshold: 检测变动的阈值
        concat: 是否拼接保留的视频
        time_box: 时间戳区域的坐标 (x1, y1, x2, y2)，这个区域会被忽略
        ratio_threshold: 变化像素占比阈值（百分比），超过这个比例才认为有变动
    """
    folder = Path(folder_path)
    video_extensions = ['.mp4', '.avi', '.mkv']
    
    # 存储保留的视频文件路径
    kept_videos = []
    
    for video_file in folder.glob('**/*'):
        if video_file.suffix.lower() in video_extensions:
            print(f"正在处理视频: {video_file}")
            if not check_video_motion(video_file, threshold, time_box, ratio_threshold):
                print(f"删除无变动视频: {video_file}")
                if os.path.exists(video_file):
                    os.remove(video_file)
                else:
                    print(f"文件不存在: {video_file}")
            else:
                print(f"保留有变动视频: {video_file}")
                kept_videos.append(video_file)
    
    if concat and kept_videos:
        output_path = str(folder / 'concatenated_output.mp4')
        concatenate_videos(kept_videos, output_path)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='检查视频文件夹中的视频是否有画面变动')
    parser.add_argument('folder', type=str, help='视频文件夹路径')
    parser.add_argument('--threshold', type=int, default=500, help='检测变动的阈值（默认：500）')
    parser.add_argument('--no-concat', action='store_true', help='不拼接保留的视频')
    parser.add_argument('--time-box', type=int, nargs=4, default=[0, 0, 150, 40], help='时间戳区域的坐标 (x1, y1, x2, y2)，这个区域会被忽略')
    parser.add_argument('--ratio-threshold', type=float, default=0.1, help='变化像素占比阈值（百分比），超过这个比例才认为有变动（默认：0.1）')
    
    args = parser.parse_args()
    process_video_folder(args.folder, args.threshold, not args.no_concat, tuple(args.time_box), args.ratio_threshold)
