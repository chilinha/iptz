from threading import Thread
import os
import time
import datetime
import glob
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def read_config(config_file):
    print(f"读取设置文件：{config_file}")
    ip_configs = []
    try:
        with open(config_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if "," in line and not line.startswith("#"):
                    parts = line.strip().split(',')
                    ip_part, port = parts[0].strip().split(':')
                    a, b, c, d = ip_part.split('.')
                    option = int(parts[1]) 
                    url_end = "/status" if option >= 10 else "/stat"
                    ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"
                    ip_configs.append((ip, port, option, url_end))
                    print(f"第{line_num}行：http://{ip}:{port}{url_end}添加到扫描列表")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")

def generate_ip_ports(ip, port, option):
    a, b, c, d = ip.split('.')
    if option == 2 or option == 12:
        c_extent = c.split('-')
        c_first = int(c_extent[0]) if len(c_extent) == 2 else int(c)
        c_last = int(c_extent[1]) + 1 if len(c_extent) == 2 else int(c) + 8
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last) for y in range(1, 256)]
    elif option == 0 or option == 10:
        return [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
    else:
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(256) for y in range(1, 256)]
        
def check_ip_port(ip_port, url_end):    
    try:
        url = f"http://{ip_port}{url_end}"
        resp = requests.get(url, timeout=2)
        resp.raise_for_status()
        if "Multi stream daemon" in resp.text or "udpxy status" in resp.text:
            print(f"{url} 访问成功")
            return ip_port
    except:
        return None

def scan_ip_port(ip, port, option, url_end):
    def show_progress():
        while checked[0] < len(ip_ports) and option % 2 == 1:
            print(f"已扫描：{checked[0]}/{len(ip_ports)}, 有效ip_port：{len(valid_ip_ports)}个")
            time.sleep(30)
    valid_ip_ports = []
    ip_ports = generate_ip_ports(ip, port, option)
    checked = [0]
    Thread(target=show_progress, daemon=True).start()
    with ThreadPoolExecutor(max_workers = 300 if option % 2 == 1 else 100) as executor:
        futures = {executor.submit(check_ip_port, ip_port, url_end): ip_port for ip_port in ip_ports}
        for future in as_completed(futures):
            result = future.result()
            if result:
                valid_ip_ports.append(result)
            checked[0] += 1
    return valid_ip_ports

def multicast_province(config_file):
    # 从配置文件名提取原始省份名（含序号）
    filename = os.path.basename(config_file)
    raw_prefix = filename.split('_')[0]  # 包含序号的原始前缀
    province = raw_prefix[2:]             # 友好省份名（去除前两位数字）
    
    print(f"{'='*25}\n   获取: {province} IP端口\n{'='*25}")
    
    # 读取配置
    configs = sorted(set(read_config(config_file)))
    print(f"读取完成，共需扫描 {len(configs)}组")
    
    # 扫描IP端口
    all_ip_ports = []
    for ip, port, option, url_end in configs:
        print(f"\n开始扫描  http://{ip}:{port}{url_end}")
        all_ip_ports.extend(scan_ip_port(ip, port, option, url_end))
    
    if not all_ip_ports:
        print(f"\n{province} 扫描完成，未扫描到有效IP端口")
        return
    
    # 处理扫描结果
    all_ip_ports = sorted(set(all_ip_ports))
    print(f"\n{province} 扫描完成，获取有效IP端口: {len(all_ip_ports)}个")
    
    # 定义所有文件路径
    ip_dir = 'ip'
    result_file = os.path.join(ip_dir, f"{province}_ip.txt")
    archive_file = os.path.join(ip_dir, f"存档_{province}_ip.txt")
    template_file = os.path.join('template', f"template_{province}.txt")
    
    # 保存扫描结果
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_ip_ports))
    
    # 更新存档文件
    if os.path.exists(archive_file):
        with open(archive_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    else:
        lines = []
    
    for ip_port in all_ip_ports:
        ip, port = ip_port.split(":")
        a, b, c, d = ip.split(".")
        lines.append(f"{a}.{b}.{c}.1:{port}\n")
    
    with open(archive_file, 'w', encoding='utf-8') as f:
        f.writelines(sorted(set(lines)))
    
    # 生成组播文件 - 修改点：放入zubo目录并去除"组播_"前缀
    if not os.path.exists(template_file):
        print(f"缺少模板文件: {template_file}")
        return
    
    with open(template_file, 'r', encoding='utf-8') as f:
        tem_channels = f.read()
    
    output = [f"{province},#genre#\n"]
    with open(result_file, 'r', encoding='utf-8') as f:
        for line in f:
            ip = line.strip()
            output.append(tem_channels.replace("ipipip", f"{ip}"))
    
    # 修改点1：去除"组播_"前缀
    # 修改点2：放入zubo目录
    with open(os.path.join('zubo', f"{raw_prefix}.txt"), 'w', encoding='utf-8') as f:
        f.writelines(output)

def txt_to_m3u(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    with open(output_file, 'w', encoding='utf-8') as f:
        genre = ''
        for line in lines:
            line = line.strip()
            if "," in line:
                channel_name, channel_url = line.split(',', 1)
                if channel_url == '#genre#':
                    genre = channel_name
                else:
                    f.write(f'#EXTINF:-1 group-title="{genre}",{channel_name}\n')
                    f.write(f'{channel_url}\n')

def main():
    # 确保zubo目录存在
    os.makedirs('zubo', exist_ok=True)
    
    # 处理所有配置文件
    config_files = sorted(glob.glob(os.path.join('ip', '*_config.txt')))
    for config_file in config_files:
        multicast_province(config_file)
    
    # 修改点：从zubo目录收集文件
    file_contents = []
    for file_path in sorted(glob.glob(os.path.join('zubo', '*.txt'))):
        with open(file_path, 'r', encoding="utf-8") as f:
            file_contents.append(f.read())
    
    now = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=8)
    current_time = now.strftime("%y/%m/%d %H:%M")
    with open("zubo_all.txt", "w", encoding="utf-8") as f:
        f.write(f"更新时间,#genre#\n")
        f.write(f"{current_time},http://60.29.124.66:6080/hls/1/index.m3u8\n")
        f.write('\n'.join(file_contents))
    
    txt_to_m3u("zubo_all.txt", "zubo_all.m3u")
    print(f"组播地址获取完成，共合并 {len(file_contents)} 个省份文件")

if __name__ == "__main__":
    main()
