import os
import sys
import urllib.request

def download_file(url, dest_path):
    print(f"Downloading: {url}")
    print(f"Destination: {dest_path}")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    # Custom User-Agent to avoid HTTP 403 Forbidden on Hugging Face
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
    urllib.request.install_opener(opener)
    
    last_percent = -1
    def report(block_num, block_size, total_size):
        nonlocal last_percent
        read_so_far = block_num * block_size
        if total_size > 0:
            percent = int(min(100, read_so_far * 100 / total_size))
            if percent != last_percent:
                sys.stdout.write(f"\rProgress: {percent}% ({read_so_far / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB)")
                sys.stdout.flush()
                last_percent = percent
        else:
            sys.stdout.write(f"\rProgress: {read_so_far / (1024*1024):.1f}MB")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, dest_path, reporthook=report)
        print("\nDownload finished successfully!")
    except Exception as e:
        print(f"\nFailed to download: {e}")

if __name__ == "__main__":
    # 7B Model
    model_url = "https://huggingface.co/bartowski/Qwen_Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/Qwen_Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"
    model_dest = r"C:\ameva\models\vlm\Qwen_Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"
    
    # 7B Projector
    mmproj_url = "https://huggingface.co/bartowski/Qwen_Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/mmproj-Qwen_Qwen2.5-VL-7B-Instruct-f16.gguf"
    mmproj_dest = r"C:\ameva\models\vlm\mmproj-Qwen_Qwen2.5-VL-7B-Instruct-f16.gguf"
    
    print("=== Downloading Qwen2.5-VL-7B-Instruct GGUF & Vision Projector ===")
    if os.path.exists(model_dest):
        print(f"Model file already exists at {model_dest}, skipping.")
    else:
        download_file(model_url, model_dest)
        
    print("-" * 60)
    if os.path.exists(mmproj_dest):
        print(f"Projector file already exists at {mmproj_dest}, skipping.")
    else:
        download_file(mmproj_url, mmproj_dest)
