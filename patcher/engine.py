"""Verified, streaming ISO-to-XISO patching; the source is always read-only."""
from pathlib import Path, PurePosixPath
import hashlib, json, os, shutil, struct, threading, uuid, zipfile, zlib

SECTOR = 2048
MAGIC = b'MICROSOFT*XBOX*MEDIA'

class PatchError(Exception):
    pass

def safe_path(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value or str(p) != value:
        raise PatchError('패치에 잘못된 파일 경로가 있습니다.')
    return p

class Disc:
    def __init__(self, path):
        self.path = Path(path)
        self.f = self.path.open('rb')
        self.length = self.path.stat().st_size
        try:
            for base in (0, 0x18300000, 0xfd90000, 0x2080000):
                if base + 0x10800 > self.length:
                    continue
                d = self.read(base + 0x10000, 2048)
                if d[:20] == MAGIC and d[-20:] == MAGIC:
                    self.base = base
                    sector, size = struct.unpack_from('<II', d, 20)
                    break
            else:
                raise PatchError('Xbox ISO/XISO 형식을 찾지 못했습니다.')
            self.entries = []
            self._directories = set()
            self.walk('', sector, size)
        except BaseException:
            self.close()
            raise

    def close(self):
        self.f.close()

    def read(self, offset, size):
        if offset < 0 or size < 0 or offset + size > self.length:
            raise PatchError('ISO 안의 파일 위치가 잘못됐습니다.')
        self.f.seek(offset)
        result = self.f.read(size)
        if len(result) != size:
            raise PatchError('ISO를 끝까지 읽을 수 없습니다.')
        return result

    def walk(self, parent, sector, size):
        if not size:
            return
        if len(PurePosixPath(parent).parts) > 64 or (sector,size) in self._directories:
            raise PatchError('ISO의 폴더 구조가 잘못됐습니다.')
        self._directories.add((sector,size))
        if size > 16 * 1024 * 1024:
            raise PatchError('ISO의 폴더 정보가 비정상적으로 큽니다.')
        data = self.read(self.base + sector * SECTOR, size)
        visited = set()
        def node(pos):
            if pos in visited or pos + 14 > size:
                raise PatchError('ISO의 파일 목록이 손상됐습니다.')
            visited.add(pos)
            left,right,start,length,attrs,nlen = struct.unpack_from('<HHIIBB',data,pos)
            if pos + 14 + nlen > size:
                raise PatchError('ISO의 파일 이름이 손상됐습니다.')
            try:
                name = data[pos+14:pos+14+nlen].decode('ascii')
            except UnicodeDecodeError as e:
                raise PatchError('지원하지 않는 ISO 파일 이름입니다.') from e
            if not name or name in ('.','..') or '/' in name or '\\' in name or ':' in name:
                raise PatchError('ISO의 파일 이름이 잘못됐습니다.')
            path = str(PurePosixPath(parent)/name)
            if left: node(left*4)
            entry = dict(path=path, offset=self.base+start*SECTOR, size=length, directory=bool(attrs&0x10))
            self.entries.append(entry)
            if entry['directory']: self.walk(path,start,length)
            if right: node(right*4)
        node(0)

def layout(manifest, patches):
    root = dict(name='', path='', directory=True, children=[])
    nodes = {'':root}
    for path in sorted(manifest['directories'], key=lambda s: (len(PurePosixPath(s).parts),s.upper())):
        p = safe_path(path)
        item = dict(name=p.name,path=path,directory=True,children=[])
        nodes[path] = item
        parent = str(p.parent)
        nodes['' if parent=='.' else parent]['children'].append(item)
    for row in manifest['files']:
        p = safe_path(row['path'])
        item = dict(name=p.name,path=str(p),directory=False,
                    size=patches.get(str(p),{}).get('patched_size',row['size']))
        nodes[str(p)] = item
        parent=str(p.parent)
        nodes['' if parent=='.' else parent]['children'].append(item)
    def prepare(item):
        if not item['directory']: return
        item['children'].sort(key=lambda v:v['name'].upper())
        data=bytearray()
        def place(children):
            if not children:return 0
            mid=len(children)//2; child=children[mid]; pos=len(data)
            name=child['name'].encode('ascii')
            data.extend(b'\0'*14+name)
            data.extend(b'\xff'*((-len(data))%4))
            left=place(children[:mid]); right=place(children[mid+1:])
            struct.pack_into('<HH',data,pos,left//4,right//4)
            data[pos+12]=0x10 if child['directory'] else 0x20
            data[pos+13]=len(name); child['entry_offset']=pos; child['parent']=item
            return pos
        place(item['children'])
        data.extend(b'\xff'*((-len(data))%SECTOR))
        item['table']=data; item['size']=len(data)
        for child in item['children']:prepare(child)
    prepare(root)
    ordered=[]
    def walk(item):
        ordered.append(item)
        if item['directory']:
            for child in item['children']:walk(child)
    walk(root)
    sector=34
    for item in [v for v in ordered if v['directory']]+[v for v in ordered if not v['directory']]:
        item['sector']=sector; sector+=(item['size']+SECTOR-1)//SECTOR
    for item in ordered[1:]:
        struct.pack_into('<II',item['parent']['table'],item['entry_offset']+4,item['sector'],item['size'])
    return root, ordered, (sector*SECTOR+0xffff)//0x10000*0x10000

def apply(source, destination, bundle, notify=lambda percent,message:None, cancel=None, verify_only=False):
    source=Path(source).resolve(); destination=Path(destination).resolve()
    cancel=cancel or threading.Event()
    def check():
        if cancel.is_set():raise PatchError('작업을 취소했습니다.')
    if not source.is_file():raise PatchError('원본 ISO 파일을 선택해주세요.')
    if source==destination:raise PatchError('원본과 저장할 파일의 경로가 같을 수 없습니다.')
    if destination.exists():raise PatchError('저장할 파일이 이미 있습니다. 다른 파일 이름을 선택해주세요.')
    if not destination.parent.is_dir():raise PatchError('저장할 폴더가 없습니다.')
    temporary=None; disc=None
    try:
        with zipfile.ZipFile(bundle) as z:
            metadata=json.loads(z.read('manifest.json'))
            manifest=metadata['source_files']; patches={r['path']:r for r in metadata['patches']}
            if manifest['file_count']!=6316 or len(manifest['files'])!=6316:
                raise PatchError('패치 데이터가 올바르지 않습니다.')
            disc=Disc(source)
            files={e['path']:e for e in disc.entries if not e['directory']}
            if len(files)!=6316 or set(files)!={r['path'] for r in manifest['files']}:
                raise PatchError('지원하는 일본판 원본과 파일 구성이 다릅니다.')
            expected_dirs=set(manifest['directories'])
            if {e['path'] for e in disc.entries if e['directory']}!=expected_dirs:
                raise PatchError('지원하는 일본판 원본과 폴더 구성이 다릅니다.')
            for row in manifest['files']:
                safe_path(row['path'])
                if files[row['path']]['size']!=row['size']:
                    raise PatchError('원본 파일의 크기가 다릅니다: '+row['path'])
            notify(1,'원본 ISO SHA-256을 계산합니다.')
            hasher=hashlib.sha256(); read=0
            with source.open('rb') as input_file:
                while chunk:=input_file.read(4*1024*1024):
                    check();hasher.update(chunk);read+=len(chunk)
                    notify(1+read/disc.length*14,'원본 ISO를 확인하고 있습니다.')
            source_sha=hasher.hexdigest()
            notify(15,'원본 게임 파일 6,316개를 검사합니다.')
            cached={}
            for i,row in enumerate(manifest['files'],1):
                check();entry=files[row['path']]
                data=disc.read(entry['offset'],entry['size'])
                if hashlib.sha256(data).hexdigest()!=row['sha256']:
                    raise PatchError('원본 파일이 손상됐거나 다른 판본입니다: '+row['path'])
                if row['path'] in patches:cached[row['path']]=data
                if i%32==0 or i==6316:notify(15+i/6316*25,f'원본 파일 검사: {i:,} / 6,316')
            replacements={}
            for path,row in patches.items():
                check();old=cached[path]
                if hashlib.sha256(old).hexdigest()!=row['original_sha256']:
                    raise PatchError('패치 원본 검사가 실패했습니다: '+path)
                delta=zlib.decompress(z.read(row['delta']))
                if len(delta)!=row['patched_size']:raise PatchError('패치 차분의 크기가 잘못됐습니다.')
                result=bytearray(delta)
                for i in range(min(len(old),len(result))):result[i]^=old[i]
                result=bytes(result)
                if hashlib.sha256(result).hexdigest()!=row['patched_sha256']:
                    raise PatchError('패치 차분 검사가 실패했습니다: '+path)
                replacements[path]=result
            if verify_only:
                return dict(version=metadata['version'],verified_only=True,source_sha256=source_sha,
                            source_files_verified=6316,patch_files_verified=len(replacements))
            root,nodes,size=layout(manifest,patches)
            if size!=metadata['target_size']:raise PatchError('출력 이미지 크기 검사가 실패했습니다.')
            if shutil.disk_usage(destination.parent).free<size+64*1024*1024:
                raise PatchError('저장 공간이 부족합니다. 약 1.3GB 이상의 공간을 확보해주세요.')
            descriptor=bytearray(z.read('descriptor.bin'))
            struct.pack_into('<II',descriptor,20,root['sector'],root['size'])
            temporary=destination.with_name(destination.name+'.partial-'+uuid.uuid4().hex)
            notify(42,'새 한국어 XISO를 만들고 있습니다.')
            with temporary.open('xb') as output:
                output.truncate(size);output.seek(0x10000);output.write(descriptor)
                total=sum(n['size'] for n in nodes);written=0
                for item in nodes:
                    check();output.seek(item['sector']*SECTOR)
                    if item['directory']:output.write(item['table'])
                    elif item['path'] in replacements:output.write(replacements[item['path']])
                    else:
                        entry=files[item['path']];left=entry['size'];pos=entry['offset']
                        while left:
                            check();chunk=disc.read(pos,min(left,4*1024*1024))
                            output.write(chunk);left-=len(chunk);pos+=len(chunk)
                    written+=item['size']
                    notify(42+written/max(total,1)*40,'한국어 XISO를 저장하고 있습니다.')
                output.flush();os.fsync(output.fileno())
            notify(82,'완성된 XISO의 SHA-256을 검사합니다.')
            digest=hashlib.sha256();read=0
            with temporary.open('rb') as input_file:
                while chunk:=input_file.read(4*1024*1024):
                    check();digest.update(chunk);read+=len(chunk)
                    notify(82+read/size*17,'완성 파일을 검증하고 있습니다.')
            actual=digest.hexdigest()
            if actual!=metadata['target_sha256']:
                raise PatchError('완성 이미지의 SHA-256이 일치하지 않습니다. 출력 파일을 폐기했습니다.')
            check()
            if destination.exists():raise PatchError('저장 경로에 파일이 생겼습니다. 덮어쓰지 않습니다.')
            # Windows rename fails if a destination appeared concurrently.
            temporary.rename(destination);temporary=None
            notify(100,'한국어 패치를 완료했습니다.')
            return dict(version=metadata['version'],output=str(destination),size=size,
                        source_sha256=source_sha,target_sha256=actual,source_files_verified=6316,
                        patch_files_verified=len(replacements),source_preserved=True)
    finally:
        if disc:disc.close()
        if temporary is not None:temporary.unlink(missing_ok=True)
