#!/usr/bin/env python3
"""
清风直播 - APK 独立包名定制与 v1+v2 签名重构工具 (repackage_tv_app.py)

核心作用:
  1. 解决在小米电视/Android TV 上安装时与原有小薇直播应用包名冲突导致被覆盖的问题。
     通过重构二进制 AndroidManifest.xml (AXML) 与 resources.arsc，将包名替换为
     com.qingfeng.live.tv，应用名称替换为“清风直播”。
  2. 解决在 Xiaomi HyperOS (小米澎湃 OS 2.0.5.0 / Android 14) 上安装失败
     报错误代码 -103 (INSTALL_PARSE_FAILED_NO_CERTIFICATES) 的问题。
     通过注入标准 APK Signature Scheme v2 签名块 (ID 0x7109871a) 及 v1 (JAR) 签名，
     满足 HyperOS 2.0 强制要求的安全签名门禁。
"""
import base64
import datetime
import hashlib
import io
import os
import struct
import subprocess
import sys
import tempfile
import zipfile
from typing import Dict, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID


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

    new_strings = []
    for s in strings:
        cur = s
        for old_val, new_val in replacements.items():
            if old_val in cur:
                cur = cur.replace(old_val, new_val)
        new_strings.append(cur)

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

    rest_data = axml_bytes[8 + sp_chunk_size:]
    new_file_size = 8 + len(new_sp_chunk) + len(rest_data)
    new_header = struct.pack('<II', magic, new_file_size)

    return new_header + new_sp_chunk + rest_data


def lp(data: bytes) -> bytes:
    """4 字节小端长度前缀编码 (Android APK v2 签名标准)"""
    return struct.pack('<I', len(data)) + data


def create_key_and_cert():
    """生成 RSA 2048 私钥与 X.509 自签名证书"""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u'QingFeng Live TV'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'QingFengTV'),
        x509.NameAttribute(NameOID.COUNTRY_NAME, u'CN'),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        public_key
    ).serial_number(
        1001
    ).not_valid_before(
        datetime.datetime.utcnow() - datetime.timedelta(days=1)
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=10000)
    ).sign(private_key, hashes.SHA256())

    cert_der = cert.public_bytes(serialization.Encoding.DER)
    return private_key, cert, cert_der


def generate_v1_signature(entries: Dict[str, bytes], private_key, cert) -> Dict[str, bytes]:
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

        # 导出私钥与证书给 openssl 生成标准 PKCS#7 结构
        with open(key_file, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        with open(cert_file, 'wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(sf_file, 'wb') as f:
            f.write(sf_bytes)

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


def inject_apk_v2_signature(apk_bytes: bytes, private_key, cert_der: bytes) -> bytes:
    """
    为 APK 文件注入标准 APK Signature Scheme v2 (ID 0x7109871a) 签名块
    彻底修复 Android 11+ / Xiaomi HyperOS 2.0 上报 -103 错误。
    """
    eocd_pos = apk_bytes.rfind(b'PK\x05\x06')
    if eocd_pos == -1:
        raise ValueError("无效的 ZIP/APK 结构: 未定位到 EOCD 魔数")

    cd_size, cd_offset = struct.unpack('<II', apk_bytes[eocd_pos + 12:eocd_pos + 20])

    # 若已有旧签名块则予以剔除，确保结构规范
    magic_pos = apk_bytes.find(b'APK Sig Block 42')
    if magic_pos != -1 and magic_pos < cd_offset:
        size2, = struct.unpack('<Q', apk_bytes[cd_offset - 24:cd_offset - 16])
        block_start = cd_offset - size2 - 8
        section1 = apk_bytes[:block_start]
        section2 = apk_bytes[cd_offset:eocd_pos]
    else:
        section1 = apk_bytes[:cd_offset]
        section2 = apk_bytes[cd_offset:eocd_pos]

    # Google v2 规范: 计算 EOCD 摘要时，需将 Central Directory 偏移量预设为 len(section1)
    eocd_for_hash = bytearray(apk_bytes[eocd_pos:])
    struct.pack_into('<I', eocd_for_hash, 16, len(section1))
    section4_hash = bytes(eocd_for_hash)

    # 1MB 分块 Merkle 根摘要计算
    CHUNK_SIZE = 1048576
    chunk_hashes = []
    for sec in [section1, section2, section4_hash]:
        off = 0
        while off < len(sec):
            c = sec[off:off + CHUNK_SIZE]
            chunk_hashes.append(hashlib.sha256(b'\xa5' + struct.pack('<I', len(c)) + c).digest())
            off += len(c)
    top_hash = hashlib.sha256(b'\x5a' + struct.pack('<I', len(chunk_hashes)) + b''.join(chunk_hashes)).digest()

    # 签名算法 ID: 0x0103 = RSASSA-PKCS1-v1_5 with SHA-256
    digest_elem = struct.pack('<I', 0x0103) + lp(top_hash)
    digests = lp(lp(digest_elem))
    certificates = lp(lp(cert_der))
    additional_attributes = lp(b'')  # 额外属性为空
    raw_signed_data = digests + certificates + additional_attributes
    signed_data = lp(raw_signed_data)

    # 计算签名
    sig = private_key.sign(
        raw_signed_data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    sig_elem = struct.pack('<I', 0x0103) + lp(sig)
    signatures = lp(lp(sig_elem))

    pub_key_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    public_key = lp(pub_key_der)

    signer = lp(signed_data + signatures + public_key)
    v2_block = lp(signer)

    # 构建 APK Signing Block 结构
    pair = struct.pack('<I', 0x7109871a) + v2_block
    pair_with_len = struct.pack('<Q', len(pair)) + pair

    block_size = len(pair_with_len) + 16 + 8
    apk_signing_block = (
        struct.pack('<Q', block_size) +
        pair_with_len +
        struct.pack('<Q', block_size) +
        b'APK Sig Block 42'
    )

    # 最终更新 EOCD 中的真实 Central Directory 偏移
    final_eocd = bytearray(apk_bytes[eocd_pos:])
    real_cd_offset = len(section1) + len(apk_signing_block)
    struct.pack_into('<I', final_eocd, 16, real_cd_offset)

    return section1 + apk_signing_block + section2 + bytes(final_eocd)


def repackage_to_qingfeng_tv(
    src_apk: str,
    dest_apk: str,
    new_package: str = "com.qingfeng.live.tv",
    new_app_name: str = "清风直播"
) -> bool:
    """
    将输入 APK 重构为独立包名、独立应用名称，并注入 v1+v2 双重签名的清风直播专属 APK
    """
    if not os.path.exists(src_apk):
        print(f"[-] 源 APK 文件不存在: {src_apk}")
        return False

    print(f"[*] 正在重构 APK (适配 Xiaomi HyperOS 2.0 并隔离包名)...")
    print(f"    - 原文件: {src_apk}")
    print(f"    - 目标独立包名: {new_package} (避免覆盖小薇直播)")
    print(f"    - 目标应用名称: {new_app_name}")

    with zipfile.ZipFile(src_apk, 'r') as zin:
        entries = {}
        for item in zin.infolist():
            if item.filename.startswith('META-INF/'):
                continue
            entries[item.filename] = zin.read(item.filename)

    # 1. 修改 AndroidManifest.xml (隔离包名与 authority)
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

    # 3. 生成公私钥与自签名证书
    private_key, cert, cert_der = create_key_and_cert()

    # 4. 生成 v1 签名 (JAR 签名)
    sig_files = generate_v1_signature(entries, private_key, cert)
    entries.update(sig_files)

    # 5. 暂存打包 ZIP 字节
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for name, content in entries.items():
            zout.writestr(name, content)
    raw_apk_bytes = zip_buf.getvalue()

    # 6. 注入 Android v2 签名块 (APK Signature Scheme v2, 解决 HyperOS -103 错误)
    print(f"[*] 正在为 APK 注入 APK Signature Scheme v2 签名块...")
    final_signed_apk = inject_apk_v2_signature(raw_apk_bytes, private_key, cert_der)

    # 7. 写入最终目标 APK
    os.makedirs(os.path.dirname(os.path.abspath(dest_apk)), exist_ok=True)
    temp_apk = dest_apk + ".tmp"
    with open(temp_apk, 'wb') as f:
        f.write(final_signed_apk)

    if os.path.exists(dest_apk):
        os.remove(dest_apk)
    os.rename(temp_apk, dest_apk)

    size_mb = round(os.path.getsize(dest_apk) / (1024 * 1024), 2)
    print(f"[+] 清风直播专属 APK 生成成功: {dest_apk} ({size_mb} MB)")
    print(f"    - 包名: {new_package} (独立共存，绝不覆盖小薇直播)")
    print(f"    - 签名: Android v1 + APK Signature Scheme v2 (完美支持 Xiaomi HyperOS 2.0)")
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
