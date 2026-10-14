#!/usr/bin/env python3
# 把改写后的模块映像直接写成一个苹果格式的动态库 Guest.framework/Guest：只装段，没有符号，没有代码之外的任何东西。
# 只用 Python 标准库，不调用编译器、链接器或任何苹果工具，在 macOS / Linux / Windows 上产出逐字节相同的文件。
# 给谁用：壳安装包（ios/tools/shell_build.sh）不含游戏程序；使用者用自己的游戏文件改写出模块映像后，由 d2rm_pack.py 调本脚本
# 写出这个库、放进安装包的 Frameworks/，再用自签工具整包签名。宿主的装载器（host/loader.c 的 DM_SHELL 分支）加载它并按节名取段。
#
# 节的布局与内嵌做法（ios/tools/gen_embed.py）一致，装载器不用分两套：
#   __TEXT,__dm<名>x0   原 text：[0, 圆整16K(TEXT_END))
#   __DM<名>W,__img     可写段：[圆整16K(TEXT_END), PATCH_OFF)
#   __TEXT,__dm<名>x1   补丁区：[PATCH_OFF, 圆整16K(文件尾))
# 文件格式上要注意的三点（都是真机 / Mac 上实测出来的）：
#   · 必须声明依赖 /usr/lib/libSystem.B.dylib，否则系统拒绝加载（「must link with at least libSystem.dylib」）；
#   · 每个节按 16K 对齐、整页大小：装载器用 vm_remap 按整页取；
#   · __LINKEDIT 放在最后并留在文件末尾：签名工具把签名追加在它后面。
#   · 产出时顺带写入一个 ad-hoc 签名并预留重签空间（adhoc_sign，等价 ldid -S）：整包签名工具（Sideloadly 等）会覆盖重签，行为不变；
#     像 LiveContainer 这样在手机上现场签 guest 的工具，面对「完全没签过」的库会直接失败（实测 r41 包报 Failed to Sign），有了这个占位它就能原位替换。
#   · 要回到旧行为（完全不写签名）用 --unsigned。
# 用法：guest_dylib.py <产物目录> <输出目录> <模块名...>     输出 <输出目录>/Guest.framework/{Guest,Info.plist}
# Write the rewritten module images directly as one Apple-format dynamic library Guest.framework/Guest: it holds only segments, no symbols, and nothing other than the code.
# Uses only the Python standard library, calls no compiler, linker or any Apple tool, and produces byte-for-byte identical files on macOS / Linux / Windows.
# Who it is for: the shell install package (ios/tools/shell_build.sh) contains no game program; after users rewrite the module images from their own game files, d2rm_pack.py calls this script
# to write this library and put it into the install package's Frameworks/, and then the whole package is signed with a sideloading tool. The host's loader (the DM_SHELL branch of host/loader.c) loads it and fetches the segments by section name.
# The section layout matches the embedded approach (ios/tools/gen_embed.py), so the loader does not need two variants:
#   __TEXT,__dm<name>x0   original text: [0, round16K(TEXT_END))
#   __DM<name>W,__img     writable segment: [round16K(TEXT_END), PATCH_OFF)
#   __TEXT,__dm<name>x1   patch area: [PATCH_OFF, round16K(end of file))
# Three points to note about the file format (all found by measurement on a real device / Mac):
#   · a dependency on /usr/lib/libSystem.B.dylib must be declared, otherwise the system refuses to load it ("must link with at least libSystem.dylib");
#   · every section is aligned to 16K and is a whole number of pages: the loader takes whole pages with vm_remap;
#   · __LINKEDIT goes last and stays at the end of the file: the signing tool appends the signature after it.
#   · The output also carries a pre-written ad-hoc signature with room to re-sign (adhoc_sign, equivalent to ldid -S): whole-package
#     signing tools (Sideloadly etc.) simply re-sign over it, behaviour unchanged; tools that sign the guest on the phone at install
#     time, like LiveContainer, fail on a library that was never signed at all (Failed to Sign, seen with the r41 package) -- with this
#     placeholder they can replace it in place.
#   · Pass --unsigned to get the old behaviour (no signature written at all).
# Usage: guest_dylib.py <build output directory> <output directory> <module name...>     writes <output directory>/Guest.framework/{Guest,Info.plist}
import hashlib, os, struct, sys

PG = 0x4000
MIN_IOS = 26 << 16   # 与工程的最低系统版本一致（ios/project.yml） | matches the project's minimum system version (ios/project.yml)


def r16(x): return (x + PG - 1) & ~(PG - 1)


def s16(s):
    b = s.encode(); assert len(b) <= 16, s; return b.ljust(16, b'\0')


def segment(name, addr, size, fileoff, filesize, prot, sects):
    b = struct.pack('<II16sQQQQiiII', 0x19, 72 + 80 * len(sects), s16(name), addr, size, fileoff, filesize, prot, prot, len(sects), 0)
    for sn, a, sz, flags in sects:
        b += struct.pack('<16s16sQQIIIIIIII', s16(sn), s16(name), a, sz, a, 14, 0, 0, flags, 0, 0, 0)   # 文件偏移 = 地址；对齐 2^14 | file offset = address; alignment 2^14
    return b


def dylib_cmd(cmd, name):
    name += b'\0' * (8 - len(name) % 8)
    return struct.pack('<IIIIII', cmd, 24 + len(name), 24, 2, 0x10000, 0x10000) + name


def adhoc_sign(img, text_vmsize, ident):
    # 给无签名的库追加 ad-hoc 签名并预留重签空间。签名是苹果格式（SuperBlob：代码目录 + 空要求集），全程大端；
    # 页散列按 4K 算（代码目录的 pageSize 与段 16K 对齐是两回事）。datasize 比实际签名多留 32K：
    # 现场重签的工具（LiveContainer）要把带证书的签名（CMS 几 KB）原位写进来、不必改文件大小；整包重签的工具（Sideloadly）自会改写 LC。
    # Append an ad-hoc signature to the unsigned library and reserve room to re-sign. The signature is Apple format (a SuperBlob:
    # a code directory + an empty requirement set), big-endian throughout; page hashes are 4K (the directory's pageSize is a separate
    # thing from the 16K segment alignment). datasize keeps 32K more than the actual signature: a tool that signs on the spot
    # (LiveContainer) writes its certificate signature (a few KB of CMS) in place without growing the file; a whole-package re-signer
    # (Sideloadly) rewrites the LC itself.
    dataoff = (len(img) + 15) & ~15
    ident_b = ident.encode() + b'\0'
    nslots = (dataoff + 0xFFF) // 0x1000
    cd_len = 68 + len(ident_b) + nslots * 32
    cd = struct.pack('>9IBBBBI3Q', 0xFADE0C02, cd_len, 0x20400, 2, 68 + len(ident_b), 68, 0, nslots, dataoff,
                     32, 2, 0, 12, 0, 0, text_vmsize, 0) + ident_b + b'\0' * (nslots * 32)   # 散列先占位 | hashes are placeholders for now
    req = struct.pack('>III', 0xFADE0C01, 12, 0)   # 空要求集 | empty requirement set
    # 索引区从 SuperBlob 头 12 字节之后开始（magic+length+count），两个条目占 16 字节，故第一个 blob 在偏移 28
    # the index starts after the 12-byte SuperBlob header (magic+length+count); two entries take 16 bytes, so the first blob sits at 28
    sb = struct.pack('>III', 0xFADE0CC0, 28 + len(cd) + len(req), 2) + struct.pack('>II', 0, 28) \
        + struct.pack('>II', 2, 28 + len(cd)) + cd + req
    reserved = ((len(sb) + 15) & ~15) + 0x8000
    out = bytearray(img.ljust(dataoff, b'\0') + sb + b'\0' * (reserved - len(sb)))
    # 填 LC_CODE_SIGNATURE 的 dataoff/datasize（签名命令是最后一条），并让 __LINKEDIT 罩住整个签名区（与苹果自己签的库一致）
    # Fill in dataoff/datasize of LC_CODE_SIGNATURE (the signature command is the last one) and make __LINKEDIT cover the whole
    # signature area (as in Apple's own signed libraries)
    ncmds, sizeofcmds = struct.unpack_from('<II', out, 16)
    sig_off = 32 + sizeofcmds - 16
    assert struct.unpack_from('<I', out, sig_off)[0] == 0x1d, 'LC_CODE_SIGNATURE 必须是最后一条装载命令 | LC_CODE_SIGNATURE must be the last load command'
    struct.pack_into('<IIII', out, sig_off, 0x1d, 16, dataoff, reserved)
    off, seen = 32, False
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', out, off)
        if cmd == 0x19 and out[off + 8:off + 18] == b'__LINKEDIT':
            fo, = struct.unpack_from('<Q', out, off + 40)   # fileoff 在 +40；vmsize +32、filesize +48 不混 | fileoff at +40; vmsize +32, filesize +48
            fs = dataoff + reserved - fo
            struct.pack_into('<Q', out, off + 32, (fs + 0x3FFF) & ~0x3FFF)
            struct.pack_into('<Q', out, off + 48, fs)
            seen = True
        off += size
    assert seen, '__LINKEDIT 段没找到 | __LINKEDIT segment not found'
    # 散列最后算：第一页里刚填的 dataoff/datasize 与改过的 __LINKEDIT 也必须被覆盖到；尾页不足 4K 补零
    # Hashes come last: the first page just patched (LC dataoff/datasize, __LINKEDIT) must be covered too; the last page is zero-padded to 4K
    slots = dataoff + 28 + 68 + len(ident_b)
    for i in range(nslots):
        page = bytes(out[i * 0x1000:min((i + 1) * 0x1000, dataoff)]).ljust(0x1000, b'\0')
        struct.pack_into('32s', out, slots + i * 32, hashlib.sha256(page).digest())
    return bytes(out)


def build(out, names, sign=True, ident='local.guest'):
    text, wsegs = [], []
    for n in names:
        hdr = dict(l[2:].split() for l in open(os.path.join(out, n + '.fixups.tsv')) if l.startswith('# '))
        te, po = int(hdr['TEXT_END'], 16), int(hdr['PATCH_OFF'], 16)
        img = open(os.path.join(out, n + '.patched.bin'), 'rb').read(); sz = len(img); a, end = r16(te), r16(sz)
        assert po % PG == 0 and a <= po <= end, (n, hex(te), hex(po), hex(sz))
        cut = lambda lo, hi: img[lo:min(hi, sz)].ljust(hi - lo, b'\0')
        text += [('__dm%sx0' % n, cut(0, a)), ('__dm%sx1' % n, cut(po, end))]
        wsegs.append(('__DM%sW' % n, cut(a, po)))
    off = PG; tsects = []; body = b''          # 第一页：文件头与装载命令 | first page: file header and load commands
    for sn, b in text:
        tsects.append((sn, off, len(b), 0x80000400)); body += b; off += len(b)   # 纯指令节 | pure instructions section
    text_vmsize = off
    cmds = [segment('__TEXT', 0, off, 0, off, 5, tsects)]
    for sn, b in wsegs:
        cmds.append(segment(sn, off, len(b), off, len(b), 3, [('__img', off, len(b), 0)])); body += b; off += len(b)
    strtab = b'\0' * 8
    uuid = hashlib.sha256(body).digest()[:16]   # 由内容定：同样的输入在哪台机器上出的库都逐字节相同 | determined by content: the same input yields a byte-for-byte identical library on whatever machine it is built
    cmds += [segment('__LINKEDIT', off, PG, off, len(strtab), 1, []),
             dylib_cmd(0xd, b'@rpath/Guest.framework/Guest'),                    # LC_ID_DYLIB
             struct.pack('<II10I', 0x80000022, 48, *([0] * 10)),                 # LC_DYLD_INFO_ONLY：没有重定位、没有绑定、没有导出 | LC_DYLD_INFO_ONLY: no relocations, no bindings, no exports
             struct.pack('<IIIIII', 0x2, 24, off, 0, off, len(strtab)),          # LC_SYMTAB：0 个符号 | LC_SYMTAB: 0 symbols
             struct.pack('<II18I', 0xb, 80, *([0] * 18)),                        # LC_DYSYMTAB
             struct.pack('<II16s', 0x1b, 24, uuid),                              # LC_UUID
             struct.pack('<IIIIII', 0x32, 24, 2, MIN_IOS, MIN_IOS, 0),           # LC_BUILD_VERSION：平台 2 = iOS | LC_BUILD_VERSION: platform 2 = iOS
             dylib_cmd(0xc, b'/usr/lib/libSystem.B.dylib')]                      # LC_LOAD_DYLIB
    lc = b''.join(cmds); assert 32 + len(lc) + (16 if sign else 0) <= PG
    if sign: lc += struct.pack('<IIII', 0x1d, 16, 0, 0)   # dataoff/datasize 由 adhoc_sign 填 | filled in by adhoc_sign
    mh = struct.pack('<IiiIIIII', 0xfeedfacf, 0x0100000c, 0, 6, len(cmds) + (1 if sign else 0), len(lc), 0x00100085, 0)   # arm64、动态库 | arm64, dynamic library
    img = (mh + lc).ljust(PG, b'\0') + body + strtab
    return adhoc_sign(img, text_vmsize, ident) if sign else img


INFO_PLIST = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Guest</string>
<key>CFBundleIdentifier</key><string>%s</string>
<key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
<key>CFBundleName</key><string>Guest</string>
<key>CFBundlePackageType</key><string>FMWK</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>MinimumOSVersion</key><string>26.0</string>
<key>CFBundleSupportedPlatforms</key><array><string>iPhoneOS</string></array>
</dict></plist>
'''


def write(out, dst, names, bundle_id='local.guest', sign=True):
    fw = os.path.join(dst, 'Guest.framework'); os.makedirs(fw, exist_ok=True)
    data = build(out, names, sign=sign, ident=bundle_id)
    with open(os.path.join(fw, 'Guest'), 'wb') as f: f.write(data)
    with open(os.path.join(fw, 'Info.plist'), 'w', encoding='utf-8', newline='\n') as f: f.write(INFO_PLIST % bundle_id)
    return fw, len(data)


if __name__ == '__main__':
    args = sys.argv[1:]
    sign = True
    if args and args[0] == '--unsigned': sign = False; args = args[1:]   # 旧行为：完全不写签名 | old behaviour: no signature at all
    if len(args) < 3: sys.exit(__doc__ or '用法：guest_dylib.py [--unsigned] <产物目录> <输出目录> <模块名...>')
    fw, n = write(args[0], args[1], args[2:], sign=sign)
    print('%s：%d 字节' % (fw, n))
