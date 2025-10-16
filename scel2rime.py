#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCEL to RIME YAML Converter
简易版搜狗词库转RIME词库工具
支持单个文件转换
"""

import struct
import sys
import os
import argparse
from datetime import datetime

def byte2str(data):
    """将UTF-16LE字节码转为字符串"""
    i = 0
    length = len(data)
    ret = ''
    while i < length:
        try:
            # 每次读取两个字节（UTF-16LE）
            char_code = struct.unpack('<H', data[i:i+2])[0]
            ret += chr(char_code)
            i += 2
        except:
            i += 2
    return ret

def parse_scel(file_path):
    """解析SCEL文件"""
    print(f"正在读取文件: {file_path}")
    
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # 检查文件头
    if data[:12] != b'\x40\x15\x00\x00\x44\x43\x53\x01\x01\x00\x00\x00':
        print("❌ 错误：不是有效的搜狗SCEL词库文件")
        return None
    
    # 拼音表偏移
    start_py = 0x1540
    # 汉语词组表偏移
    start_chinese = 0x2628
    
    print("🔍 正在解析拼音表...")
    
    # 解析拼音表
    py_table = {}
    py_data = data[start_py:]
    
    pos = 0
    length = len(py_data)
    py_count = 0
    
    while pos < length:
        try:
            # 拼音索引（2字节）
            index = struct.unpack('<H', py_data[pos:pos+2])[0]
            pos += 2
            
            # 拼音长度（2字节）
            py_len = struct.unpack('<H', py_data[pos:pos+2])[0]
            pos += 2
            
            # 拼音内容
            py_str = byte2str(py_data[pos:pos+py_len])
            pos += py_len
            
            py_table[index] = py_str
            py_count += 1
            
        except Exception as e:
            pos += 1
            if pos >= length:
                break
    
    print(f"✅ 拼音表解析完成，共 {py_count} 个拼音")
    
    # 解析中文词组表
    print("🔍 正在解析中文词组...")
    
    chinese_data = data[start_chinese:]
    entries = []
    
    pos = 0
    length = len(chinese_data)
    entry_count = 0
    error_count = 0
    
    while pos < length:
        try:
            # 同音词数量（2字节）
            same_count = struct.unpack('<H', chinese_data[pos:pos+2])[0]
            pos += 2
            
            # 拼音索引表长度（2字节）
            py_table_len = struct.unpack('<H', chinese_data[pos:pos+2])[0]
            pos += 2
            
            # 解析拼音索引表
            py_indices = []
            for _ in range(py_table_len // 2):
                py_index = struct.unpack('<H', chinese_data[pos:pos+2])[0]
                py_indices.append(py_index)
                pos += 2
            
            # 获取拼音字符串
            pinyin_parts = []
            for index in py_indices:
                if index in py_table:
                    pinyin_parts.append(py_table[index])
            
            if not pinyin_parts:
                pos += same_count * (4 + 10)  # 跳过这个词组
                continue
            
            pinyin = ' '.join(pinyin_parts)
            
            # 解析每个同音词
            for _ in range(same_count):
                # 中文词组长度（2字节）
                word_len = struct.unpack('<H', chinese_data[pos:pos+2])[0]
                pos += 2
                
                # 中文词组内容
                word = byte2str(chinese_data[pos:pos+word_len])
                pos += word_len
                
                # 扩展信息长度（2字节）
                ext_len = struct.unpack('<H', chinese_data[pos:pos+2])[0]
                pos += 2
                
                # 词频（前2字节）
                freq = struct.unpack('<H', chinese_data[pos:pos+2])[0]
                pos += ext_len
                
                # 过滤空词和过长的词
                if word and 1 <= len(word) <= 8:
                    entries.append((word, pinyin, freq))
                    entry_count += 1
                    
        except Exception as e:
            error_count += 1
            pos += 1
            if pos >= length:
                break
    
    print(f"✅ 中文词组解析完成")
    print(f"📊 统计：")
    print(f"   - 有效词条：{entry_count}")
    print(f"   - 解析错误：{error_count}")
    
    return entries

def generate_rime_yaml(entries, output_file, source_file, min_freq=1, min_length=1, max_length=8):
    """生成RIME YAML词库"""
    
    # 应用过滤条件
    filtered_entries = []
    for word, pinyin, freq in entries:
        if (freq >= min_freq and 
            min_length <= len(word) <= max_length):
            filtered_entries.append((word, pinyin, freq))
    
    # 按词频排序（降序）
    filtered_entries.sort(key=lambda x: x[2], reverse=True)
    
    # 创建文件头
    yaml_header = f"""# RIME词库
# 来源：{os.path.basename(source_file)}
# 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 原始词条：{len(entries)}
# 过滤后词条：{len(filtered_entries)}
# 过滤条件：词频≥{min_freq}，长度{min_length}-{max_length}字

---
name: {os.path.splitext(os.path.basename(output_file))[0]}
version: "1.0"
sort: by_weight
use_preset_vocabulary: true
import_tables:
  - luna_pinyin
...

"""
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(yaml_header)
            
            for word, pinyin, freq in filtered_entries:
                # RIME格式：词语 拼音 词频
                f.write(f"{word}\t{pinyin}\t{freq}\n")
        
        print(f"✅ 文件保存成功：{output_file}")
        print(f"📋 文件信息：")
        print(f"   - 编码格式：UTF-8")
        print(f"   - 文件大小：{os.path.getsize(output_file) // 1024} KB")
        print(f"   - 词条数量：{len(filtered_entries)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 文件保存失败：{e}")
        return False

def show_help():
    """显示帮助信息"""
    print("=" * 60)
    print("SCEL to RIME Converter")
    print("搜狗词库转RIME词库工具")
    print("=" * 60)
    print("\n用法：")
    print("  python scel2rime.py [选项] <输入文件.scel> <输出文件.dict.yaml>")
    print("\n选项：")
    print("  -h, --help          显示帮助信息")
    print("  -f, --freq 数字     设置最小词频（默认：1）")
    print("  -min, --min-length 数字 设置最小词语长度（默认：1）")
    print("  -max, --max-length 数字 设置最大词语长度（默认：8）")
    print("\n示例：")
    print("  python scel2rime.py input.scel output.dict.yaml")
    print("  python scel2rime.py -f 5 -min 2 -max 4 input.scel output.dict.yaml")
    print("\n输出文件格式：")
    print("  词语\t拼音\t词频")
    print("  例如：\n  英雄联盟\tying xiong lian meng\t100")
    print("=" * 60)

def main():
    """主函数"""
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='SCEL to RIME Converter')
    parser.add_argument('input_file', nargs='?', help='输入SCEL文件路径')
    parser.add_argument('output_file', nargs='?', help='输出YAML文件路径')
    parser.add_argument('-f', '--freq', type=int, default=1, help='最小词频（默认：1）')
    parser.add_argument('-min', '--min-length', type=int, default=1, help='最小词语长度（默认：1）')
    parser.add_argument('-max', '--max-length', type=int, default=8, help='最大词语长度（默认：8）')
    
    args = parser.parse_args()
    
    # 检查参数
    if not args.input_file or not args.output_file:
        show_help()
        sys.exit(1)
    
    input_file = args.input_file
    output_file = args.output_file
    
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"❌ 错误：文件 '{input_file}' 不存在")
        sys.exit(1)
    
    if not input_file.endswith('.scel'):
        print(f"❌ 错误：输入文件必须是.scel格式")
        sys.exit(1)
    
    # 检查输出文件格式
    if not output_file.endswith('.dict.yaml'):
        print(f"⚠️  警告：建议输出文件以.dict.yaml结尾")
    
    print("=" * 60)
    print("开始转换...")
    print(f"输入文件：{input_file}")
    print(f"输出文件：{output_file}")
    print(f"过滤条件：词频≥{args.freq}，长度{args.min_length}-{args.max_length}字")
    print("=" * 60)
    
    # 解析SCEL文件
    entries = parse_scel(input_file)
    
    if entries:
        print("\n📝 开始生成RIME词库...")
        
        # 生成YAML文件
        success = generate_rime_yaml(
            entries, 
            output_file, 
            input_file,
            min_freq=args.freq,
            min_length=args.min_length,
            max_length=args.max_length
        )
        
        if success:
            print("\n" + "=" * 60)
            print("🎉 转换完成！")
            print("\n下一步操作：")
            print("1. 将生成的.dict.yaml文件复制到RIME配置目录：")
            print("   - Windows: %APPDATA%\\Rime\\")
            print("   - Linux: ~/.config/fcitx/rime/")
            print("   - MacOS: ~/Library/Rime/")
            print("\n2. 创建或编辑配置文件（如luna_pinyin.custom.yaml）：")
            print("   patch:")
            print("     \"translator/import_tables\":")
            print("       - luna_pinyin")
            print(f"       - {os.path.splitext(os.path.basename(output_file))[0]}")
            print("\n3. 右键点击RIME图标，选择\"重新部署\"")
            print("=" * 60)
        else:
            print("❌ 转换失败")
    else:
        print("❌ 无法解析输入文件")

if __name__ == "__main__":
    main()