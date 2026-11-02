"""Spikeout Battle Street Korean v0.8: Windows GUI and testable CLI."""
from pathlib import Path
import argparse,json,queue,sys,threading,time,traceback
from engine import apply, PatchError

def bundle_path():
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'patch-data.zip'

def gui():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    root=tk.Tk();root.title('Spikeout Battle Street 한국어 패처 v0.8')
    root.geometry('740x490');root.minsize(680,460)
    style=ttk.Style(root);style.theme_use('vista' if 'vista' in style.theme_names() else 'clam')
    style.configure('TLabel',font=('맑은 고딕',10));style.configure('TButton',font=('맑은 고딕',10))
    outer=ttk.Frame(root,padding=24);outer.pack(fill='both',expand=True)
    ttk.Label(outer,text='Spikeout Battle Street',font=('맑은 고딕',20,'bold')).pack(anchor='w')
    ttk.Label(outer,text='한국어 패치 v0.8 · 원본 ISO는 보존하고 새 파일을 만듭니다.').pack(anchor='w',pady=(3,18))
    source=tk.StringVar();output=tk.StringVar();status=tk.StringVar(value='일본판 원본 ISO 또는 XISO를 선택해주세요.')
    def select_source():
        p=filedialog.askopenfilename(title='일본판 원본 ISO 선택',filetypes=[('Xbox ISO / XISO','*.iso'),('모든 파일','*.*')])
        if p:
            source.set(p)
            if not output.get():output.set(str(Path(p).with_name('Spikeout-Battle-Street-KO-v0.8.xiso.iso')))
    def select_output():
        p=filedialog.asksaveasfilename(title='새 한국어 XISO 저장 위치',defaultextension='.iso',
            initialfile='Spikeout-Battle-Street-KO-v0.8.xiso.iso',filetypes=[('Xbox XISO','*.iso')])
        if p:output.set(p)
    inputs=[]
    for title,var,command in [('원본 ISO',source,select_source),('저장할 XISO',output,select_output)]:
        ttk.Label(outer,text=title).pack(anchor='w')
        row=ttk.Frame(outer);row.pack(fill='x',pady=(4,12))
        entry=ttk.Entry(row,textvariable=var);entry.pack(side='left',fill='x',expand=True)
        button=ttk.Button(row,text='찾아보기',command=command);button.pack(side='left',padx=(8,0))
        inputs.extend((entry,button))
    ttk.Label(outer,text='게임 실행에는 릴리스에 별도 첨부된 Android 전용 에뮬레이터를 사용하세요.',wraplength=680).pack(anchor='w',pady=(0,12))
    progress=ttk.Progressbar(outer,maximum=100);progress.pack(fill='x')
    ttk.Label(outer,textvariable=status,wraplength=680).pack(anchor='w',pady=(8,8))
    log=tk.Text(outer,height=4,font=('Consolas',9),wrap='word',state='disabled')
    log.pack(fill='both',expand=True)
    events=queue.Queue();cancel=threading.Event();running=False
    def append(text):
        log.configure(state='normal');log.insert('end',text+'\n');log.see('end');log.configure(state='disabled')
    def start():
        nonlocal running
        if running:return
        if not source.get() or not output.get():
            messagebox.showerror('파일 선택','원본 ISO와 저장할 XISO 위치를 선택해주세요.');return
        src,dst=source.get(),output.get();running=True;cancel.clear();start_button.configure(state='disabled')
        for w in inputs:w.configure(state='disabled')
        cancel_button.configure(state='normal');progress['value']=0
        append('원본 검사를 시작합니다. 원본 파일에는 쓰지 않습니다.')
        def work():
            try:
                last=[0.0]
                def notify(percent,message):
                    now=time.monotonic()
                    if now-last[0]>0.1 or percent==100:
                        events.put(('progress',percent,message));last[0]=now
                result=apply(src,dst,bundle_path(),notify,cancel)
                events.put(('done',result))
            except Exception as e:events.put(('error',str(e)))
        threading.Thread(target=work,daemon=True).start()
    def poll():
        nonlocal running
        try:
            while True:
                event=events.get_nowait()
                if event[0]=='progress':progress['value']=event[1];status.set(event[2]);continue
                running=False;start_button.configure(state='normal');cancel_button.configure(state='disabled')
                for w in inputs:w.configure(state='normal')
                if event[0]=='done':
                    status.set('완료: 새 한국어 XISO가 생성됐습니다.');progress['value']=100
                    append(event[1]['output']);append('SHA-256: '+event[1]['target_sha256'])
                    messagebox.showinfo('패치 완료','한국어 XISO 생성과 해시 검증을 완료했습니다.\n\n'+event[1]['output'])
                else:
                    status.set(event[1]);append(event[1]);messagebox.showerror('패치 중단',event[1])
        except queue.Empty:pass
        root.after(100,poll)
    buttons=ttk.Frame(outer);buttons.pack(fill='x',pady=(14,0))
    cancel_button=ttk.Button(buttons,text='취소',command=cancel.set,state='disabled');cancel_button.pack(side='right')
    start_button=ttk.Button(buttons,text='한국어 패치 시작',command=start);start_button.pack(side='right',padx=(0,8))
    def close():
        if running:
            cancel.set();status.set('작업을 취소하고 임시 파일을 정리하고 있습니다.')
        else:root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);poll();root.mainloop()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path);ap.add_argument('--output',type=Path)
    ap.add_argument('--bundle',type=Path,default=bundle_path())
    ap.add_argument('--report',type=Path);ap.add_argument('--verify-only',action='store_true')
    args=ap.parse_args()
    if args.source is None and args.output is None:gui();return 0
    try:
        if args.source is None or args.output is None:raise PatchError('--source와 --output을 함께 지정해주세요.')
        result=apply(args.source,args.output,args.bundle,verify_only=args.verify_only)
        code=0
    except Exception as e:
        result={'passed':False,'error':str(e)};code=1
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if sys.stdout:print(json.dumps(result,ensure_ascii=False,indent=2))
    return code

if __name__=='__main__':raise SystemExit(main())
