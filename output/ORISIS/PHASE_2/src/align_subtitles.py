import sys, re, json, subprocess, difflib, numpy as np
from faster_whisper import WhisperModel
vid, srt_in, srt_out, model = sys.argv[1:5]
a=np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',vid,'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout,np.float32)
m=WhisperModel(model,device="cpu",compute_type="int8")
segs,_=m.transcribe(a,language="fr",word_timestamps=True,condition_on_previous_text=False)
hw=[(w.start,w.end,w.word.strip()) for s in segs for w in s.words]
# texte de référence = SRT fourni (sans bandeau TurboScribe)
txt=" ".join(l for l in re.split(r"\n",open(srt_in,encoding="utf-8-sig").read().replace("\r","")) if l.strip() and not re.search(r"^\s*\d+\s*$|-->",l))
txt=re.sub(r"\(Transcrit par TurboScribe[^)]*\)","",txt)
txt=re.sub(r"(\w) '",r"\1'",txt); txt=re.sub(r" -",r"-",txt); txt=re.sub(r"\s+"," ",txt).strip()
txt=txt.replace("d '","d'").replace("l '","l'").replace("c '","c'").replace("n '","n'").replace("m '","m'")
rw=txt.split(" ")
norm=lambda s: re.sub(r"[^a-zàâçéèêëîïôûùüÿœ]","",s.lower())
sm=difflib.SequenceMatcher(None,[norm(x) for x in rw],[norm(x[2]) for x in hw],autojunk=False)
# attribuer un temps à chaque mot de référence
T=[None]*len(rw)
for op,i1,i2,j1,j2 in sm.get_opcodes():
    if op=="equal":
        for d in range(i2-i1): T[i1+d]=(hw[j1+d][0],hw[j1+d][1])
    elif j2>j1:
        s0,e0=hw[j1][0],hw[j2-1][1]; n=i2-i1
        for d in range(n): T[i1+d]=(s0+(e0-s0)*d/n, s0+(e0-s0)*(d+1)/n)
# interpoler les trous
for i in range(len(T)):
    if T[i] is None:
        p=next((T[j] for j in range(i-1,-1,-1) if T[j]),(0,0)); q=next((T[j] for j in range(i+1,len(T)) if T[j]),(p[1]+.3,p[1]+.3))
        T[i]=(p[1],q[0] if q[0]>p[1] else p[1]+.2)
# découpage en sous-titres : ponctuation, pause, ≤ 32 caractères
cues=[];cur=[]
for i,w in enumerate(rw):
    cur.append(i); line=" ".join(rw[k] for k in cur)
    nxt=T[i+1][0]-T[i][1] if i+1<len(rw) else 9
    if re.search(r"[.?!,]$",w) or nxt>0.35 or len(line)>=26 or i==len(rw)-1:
        if len(line)<12 and i+1<len(rw) and not re.search(r"[.?!]$",w) and nxt<0.35: continue
        cues.append(cur); cur=[]
def ts(t):
    ms=int(round(t*1000)); return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
out=[]
for n,c in enumerate(cues):
    st=T[c[0]][0]; en=T[c[-1]][1]
    if n+1<len(cues): en=min(max(en+0.15,st+0.7),T[cues[n+1][0]][0]-0.02)
    out.append(f"{n+1}\n{ts(st)} --> {ts(en)}\n{' '.join(rw[k] for k in c)}\n")
open(srt_out,"w",encoding="utf-8").write("\n".join(out))
print(len(cues),"cues; hyp words",len(hw),"ref words",len(rw),"match ratio",round(sm.ratio(),3))
# export JSON mot à mot (utilisé par le motion design : sous-titres karaoké)
if len(sys.argv)>5:
    json.dump([{"start":round(T[c[0]][0],3),"end":round(T[c[-1]][1],3),
                "words":[{"w":rw[k],"s":round(T[k][0],3),"e":round(T[k][1],3)} for k in c]} for c in cues],
              open(sys.argv[5],"w",encoding="utf-8"),ensure_ascii=False,indent=0)
