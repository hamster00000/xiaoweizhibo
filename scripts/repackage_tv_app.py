#!/usr/bin/env python3
"""
清风直播 - APK 独立包名定制与重构签名工具 (repackage_tv_app.py)
核心作用:
  解决在小米电视/Android TV 上安装时与原有小薇直播应用包名冲突导致被覆盖的问题。
  通过重构二进制 AndroidManifest.xml (AXML) 与 resources.arsc，将应用包名替换为
  com.qingfeng.live.tv，应用名称替换为“清风直播”，并打上合法的 Android v1 签名。
  使清风直播作为全新的独立应用与小薇直播在电视上并存，互不覆盖。
"""
import base64
import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import zipfile
from typing import Dict, Optional


def modify_axml_utf16le(axml_bytes: bytes, replacements: Dict[str, str]) -> bytes:
    """
    精确修改 Android 二进制 XML (AXML) 中的字符串池 (UTF-16LE 编码)
    更新 StringPool Header、偏移表及文件总大小。
    """
    magic, file_size = struct.unpack('<II', axml_bytes[:8])
    if magic != 0x80003:
        raise ValueError(f"非法的 Android 二进制 XML 文件头: {hex(magic)}")

    sp_type, sp_header_size = struct.unpack('<HH', axml_bytes[8:12])
    if sp_type != 0x0001:
        raise ValueError(f"预期 StringPool Chunk (0x0001)，实际为 {hex(sp_type)}")

    sp_chunk_size, scnt, stcnt, flags, sstart, ststart = struct.unpack('<IIIIII', axml_bytes[12:36])
    is_utf8 = bool(flags & (1 << 8))

    offsets = list(struct.unpack(f'<{scnt}I', axml_bytes[36:36 + scnt * 4]))
    sdata = axml_bytes[8 + sstart:8 + sstart + (ststart if stcnt > 0 else (sp_chunk_size - sstart))]

    # 解码所有字符串
    strings = []
    for off in offsets:
        if is_utf8:
            idx = off
            c = sdata[idx]
            idx += 1
            if c & 0x80:
                idx += 1
            b = sdata[idx]
            idx += 1
            if b & 0x80:
                b = ((b & 0x7f) << 8) | sdata[idx]
                idx += 1
            strings.append(sdata[idx:idx + b].decode('utf-8', errors='ignore'))
        else:
            l, = struct.unpack('<H', sdata[off:off + 2])
            strings.append(sdata[off + 2:off + 2 + l * 2].decode('utf-16le', errors='ignore'))

    # 进行精准映射替换
    new_strings = []
    for s in strings:
        cur = s
        for old_val, new_val in replacements.items():
            if old_val in cur:
                cur = cur.replace(old_val, new_val)
        new_strings.append(cur)

    # 重新序列化 StringPool 数据
    new_sdata = bytearray()
    new_offsets = []
    for s in new_strings:
        new_offsets.append(len(new_sdata))
        if is_utf8:
            utf8_b = s.encode('utf-8')
            char_len = len(s)
            byte_len = len(utf8_b)
            if char_len <= 127:
                new_sdata.append(char_len)
            else:
                new_sdata.extend([(char_len >> 8) | 0x80, char_len & 0xff])
            if byte_len <= 127:
                new_sdata.append(byte_len)
            else:
                new_sdata.extend([(byte_len >> 8) | 0x80, byte_len & 0xff])
            new_sdata.extend(utf8_b)
            new_sdata.append(0)
        else:
            char_len = len(s)
            encoded = s.encode('utf-16le')
            new_sdata.extend(struct.pack('<H', char_len))
            new_sdata.extend(encoded)
            new_sdata.extend(b'\x00\x00')

    # 4 字节边界补齐
    pad = (4 - (len(new_sdata) % 4)) % 4
    new_sdata.extend(b'\x00' * pad)

    new_sstart = 28 + scnt * 4 + stcnt * 4
    new_sp_chunk_size = new_sstart + len(new_sdata)
    if stcnt > 0:
        styles_data = axml_bytes[8 + ststart:8 + sp_chunk_size]
        new_ststart = new_sp_chunk_size
        new_sp_chunk_size += len(styles_data)
    else:
        new_ststart = 0
        styles_data = b''

    sp_header = struct.pack('<HHIIIIII', sp_type, sp_header_size, new_sp_chunk_size, scnt, stcnt, flags, new_sstart, new_ststart)
    new_sp_chunk = sp_header + struct.pack(f'<{scnt}I', *new_offsets) + bytes(new_sdata) + styles_data

    # 拼接剩余 Chunks 并更新文件总大小
    rest_data = axml_bytes[8 + sp_chunk_size:]
    new_file_size = 8 + len(new_sp_chunk) + len(rest_data)
    new_header = struct.pack('<II', magic, new_file_size)

    return new_header + new_sp_chunk + rest_data


def generate_v1_signature(entries: Dict[str, bytes]) -> Dict[str, bytes]:
    """生成合法的 Android v1 (JAR) 签名文件 (MANIFEST.MF, CERT.SF, CERT.RSA)"""
    file_entries_mf = []
    for name in sorted(entries.keys()):
        data = entries[name]
        sha1 = base64.b64encode(hashlib.sha1(data).digest()).decode('ascii')
        entry_text = f'Name: {name}\r\nSHA1-Digest: {sha1}\r\n\r\n'
        file_entries_mf.append((name, entry_text))

    mf_content = 'Manifest-Version: 1.0\r\nCreated-By: 1.0 (QingFengTV)\r\n\r\n' + ''.join([e[1] for e in file_entries_mf])
    mf_bytes = mf_content.encode('utf-8')

    mf_sha1 = base64.b64encode(hashlib.sha1(mf_bytes).digest()).decode('ascii')
    sf_content = f'Signature-Version: 1.0\r\nCreated-By: 1.0 (QingFengTV)\r\nSHA1-Digest-Manifest: {mf_sha1}\r\n\r\n'

    for name, entry_text in file_entries_mf:
        entry_sha1 = base64.b64encode(hashlib.sha1(entry_text.encode('utf-8')).digest()).decode('ascii')
        sf_content += f'Name: {name}\r\nSHA1-Digest: {entry_sha1}\r\n\r\n'

    sf_bytes = sf_content.encode('utf-8')

    with tempfile.TemporaryDirectory() as tmpdir:
        key_file = os.path.join(tmpdir, 'key.pem')
        cert_file = os.path.join(tmpdir, 'cert.pem')
        sf_file = os.path.join(tmpdir, 'CERT.SF')
        rsa_file = os.path.join(tmpdir, 'CERT.RSA')

        with open(sf_file, 'wb') as f:
            f.write(sf_bytes)

        # 生成 2048 位自签名证书与私钥
        subprocess.check_call([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-keyout', key_file,
            '-out', cert_file, '-days', '10000', '-nodes',
            '-subj', '/CN=QingFengLive/OU=TV/O=QingFengTV/C=CN'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 生成 PKCS#7 签名 (CERT.RSA)
        subprocess.check_call([
            'openssl', 'smime', '-sign', '-in', sf_file, '-out', rsa_file,
            '-outform', 'DER', '-nodetach', '-signer', cert_file, '-inkey', key_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        with open(rsa_file, 'rb') as f:
            rsa_bytes = f.read()

    return {
        'META-INF/MANIFEST.MF': mf_bytes,
        'META-INF/CERT.SF': sf_bytes,
        'META-INF/CERT.RSA': rsa_bytes
    }


def repackage_to_qingfeng_tv(
    src_apk: str,
    dest_apk: str,
    new_package: str = "com.qingfeng.live.tv",
    new_app_name: str = "清风直播"
) -> bool:
    """
    将输入 APK 重构为独立包名与独立应用名称的清风直播专用 APK
    """
    if not os.path.exists(src_apk):
        print(f"[-] 源 APK 文件不存在: {src_apk}")
        return False

    print(f"[*] 正在重构 APK，使其与小薇直播彻底区分...")
    print(f"    - 原文件: {src_apk}")
    print(f"    - 目标独立包名: {new_package} (避免覆盖小薇直播)")
    print(f"    - 目标应用名称: {new_app_name}")

    with zipfile.ZipFile(src_apk, 'r') as zin:
        entries = {}
        for item in zin.infolist():
            # 过滤旧的签名文件
            if item.filename.startswith('META-INF/'):
                continue
            entries[item.filename] = zin.read(item.filename)

    # 1. 修改 AndroidManifest.xml
    if 'AndroidManifest.xml' in entries:
        manifest_data = entries['AndroidManifest.xml']
        replacements = {
            'com.live.zd': new_package,
            '小薇直播': new_app_name,
        }
        try:
            new_manifest = modify_axml_utf16le(manifest_data, replacements)
            entries['AndroidManifest.xml'] = new_manifest
            print(f"[+] AndroidManifest.xml 包名已成功替换为: {new_package}")
        except Exception as e:
            print(f"[!] 警告: AXML 转换出错 ({e})，将保留原配置")

    # 2. 修改 resources.arsc 应用名称
    if 'resources.arsc' in entries:
        arsc_data = entries['resources.arsc']
        old_name_b = '小薇直播'.encode('utf-8')
        new_name_b = new_app_name.encode('utf-8')
        if len(old_name_b) == len(new_name_b):
            replaced_arsc = arsc_data.replace(old_name_b, new_name_b)
            entries['resources.arsc'] = replaced_arsc
            print(f"[+] resources.arsc 应用名称已成功更新为: {new_app_name}")

    # 3. 重新生成完整签名
    sig_files = generate_v1_signature(entries)
    entries.update(sig_files)

    # 4. 写入目标 APK
    os.makedirs(os.path.dirname(os.path.abspath(dest_apk)), exist_ok=True)
    temp_apk = dest_apk + ".tmp"
    with zipfile.ZipFile(temp_apk, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for name, content in entries.items():
            zout.writestr(name, content)

    if os.path.exists(dest_apk):
        os.remove(dest_apk)
    os.rename(temp_apk, dest_apk)

    size_mb = round(os.path.getsize(dest_apk) / (1024 * 1024), 2)
    print(f"[+] 清风直播专属 APK 生成成功: {dest_apk} ({size_mb} MB)")
    print(f"    电视端将作为独立应用【{new_app_name}】安装，与【小薇直播】完全共存，互不覆盖！")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python3 repackage_tv_app.py <src_apk> <dest_apk> [new_package] [new_app_name]")
        sys.exit(1)
    src = sys.argv[1]
    dest = sys.argv[2]
    pkg = sys.argv[3] if len(sys.argv) > 3 else "com.qingfeng.live.tv"
    label = sys.argv[4] if len(sys.argv) > 4 else "清风直播"
    ok = repackage_to_qingfeng_tv(src, dest, pkg, label)
    sys.exit(0 if ok else 1)
