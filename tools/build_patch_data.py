"""Build a source-dependent XOR delta bundle; never include a game image."""
from pathlib import Path
import argparse,hashlib,json,struct,sys,zipfile,zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'patcher'))
from engine import Disc

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--original',type=Path,required=True)
    p.add_argument('--patched',type=Path,required=True)
    p.add_argument('--source-manifest',type=Path,required=True)
    p.add_argument('--build-report',type=Path,required=True)
    p.add_argument('--reference-image',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    manifest=json.loads(a.source_manifest.read_text(encoding='utf-8'))
    build=json.loads(a.build_report.read_text(encoding='utf-8'))
    image=Disc(a.reference_image)
    descriptor=image.read(image.base+0x10000,2048);image.close()
    with a.reference_image.open('rb') as f:target_sha=hashlib.file_digest(f,'sha256').hexdigest()
    patches=[]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED,9) as z:
        z.writestr('descriptor.bin',descriptor)
        for i,row in enumerate(build['files']):
            old=(a.original/row['path']).read_bytes();new=(a.patched/row['path']).read_bytes()
            assert hashlib.sha256(old).hexdigest()==row['original_sha256']
            assert hashlib.sha256(new).hexdigest()==row['patched_sha256']
            overlap=min(len(old),len(new));delta=bytearray(new)
            for pos in range(overlap):delta[pos]^=old[pos]
            packed=zlib.compress(bytes(delta),9)
            decoded=bytearray(zlib.decompress(packed))
            for pos in range(overlap):decoded[pos]^=old[pos]
            assert bytes(decoded)==new
            name=f'deltas/{i:02d}.xor.z';z.writestr(name,packed)
            patches.append(dict(row,delta=name,delta_bytes=len(packed)))
        data=dict(version='v0.8',source_files=manifest,patches=patches,
                  target_size=a.reference_image.stat().st_size,target_sha256=target_sha,
                  patch_format='zlib-compressed XOR, original required',
                  game_images_included=False)
        z.writestr('manifest.json',json.dumps(data,ensure_ascii=False,separators=(',',':')))
    print(a.output,a.output.stat().st_size,'bytes;',len(patches),'round-trip verified deltas')

if __name__=='__main__':main()
