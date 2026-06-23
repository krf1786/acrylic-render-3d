#!/usr/bin/env python3
"""
prep.py  —  Turn a print PDF (with named spot/finish channels) into a
self-contained, photoreal 3D finish preview (single .html you can open & share).

USAGE
    python3 prep.py "my print file.pdf"
    python3 prep.py "my print file.pdf" output.html --width 1500

REQUIREMENTS (one-time)
    Ghostscript must be installed.  On a Mac:   brew install ghostscript
    Python packages:                            pip3 install pillow numpy

WHAT IT DOES
    1. Splits the PDF into its named spot separations (Ghostscript tiffsep).
    2. Detects which finishes are present (e.g. "Mirror Silver Gloss", "Black Matt").
    3. Auto-assigns a material to each (gloss=clearcoat, mirror/foil=metal, matte=rough, etc.).
    4. Bakes everything into one .html that renders with real environment reflections.
       You can re-tune any finish and drop in your own shop photo inside the viewer.
"""
import sys, os, re, base64, json, subprocess, tempfile, shutil, argparse

# ---------------------------------------------------------------- material rules
def classify(name):
    """Map a spot-colorant name to PBR material params. Returns dict."""
    n = name.lower()
    metal = 0; col = (0.05, 0.05, 0.055); flake = 0
    if 'silver' in n or 'chrome' in n or ('mirror' in n and 'gold' not in n) or ('foil' in n and 'gold' not in n):
        metal = 1; col = (0.95, 0.96, 1.00)
    elif 'gold' in n or 'brass' in n:
        metal = 1; col = (1.00, 0.82, 0.42)
    elif 'copper' in n or 'rose' in n or 'bronze' in n:
        metal = 1; col = (0.96, 0.64, 0.45)
    elif 'white' in n:
        col = (0.90, 0.90, 0.92)
    elif 'black' in n or n.strip() in ('k', 'process black'):
        col = (0.05, 0.05, 0.055)
    # finish / sheen
    if 'gloss' in n or 'uv' in n or 'shiny' in n or 'glossy' in n:
        rough = 0.06 if metal else 0.10; clear = 1.0
    elif 'matt' in n or 'soft' in n or 'velvet' in n:
        rough = 0.40 if metal else 0.80; clear = 0.0; flake = 1 if metal else 0
    elif 'satin' in n:
        rough = 0.25; clear = 0.4
    else:
        rough = 0.30 if metal else 0.55; clear = 0.3
    chip = '#%02x%02x%02x' % tuple(int((c ** (1/2.2)) * 255) for c in col)
    return dict(name=name, metal=metal, col=[round(c, 4) for c in col],
                rough=rough, clear=clear, flake=flake, chip=chip)

# process plate names we skip unless they actually carry ink
PROCESS = {'cyan', 'magenta', 'yellow', 'black'}

def is_process(name):
    return name.strip().lower() in PROCESS

# ---------------------------------------------------------------- extraction
def run(pdf, workdir, dpi):
    out = os.path.join(workdir, 'sep')
    cmd = ['gs', '-q', '-dBATCH', '-dNOPAUSE', '-dSAFER',
           '-sDEVICE=tiffsep', '-r%d' % dpi, '-o', out + '-%d.tif', pdf]
    subprocess.run(cmd, check=True, capture_output=True)
    files = [f for f in os.listdir(workdir) if f.endswith('.tif')]
    # parse "sep-1(Spot Name).tif"
    spots = {}
    for f in files:
        m = re.search(r'\((.+)\)\.tif$', f)
        if m:
            spots[m.group(1)] = os.path.join(workdir, f)
    return spots

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('out', nargs='?', default=None)
    ap.add_argument('--width', type=int, default=1500)
    ap.add_argument('--dpi', type=int, default=260)
    args = ap.parse_args()

    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        sys.exit("Need Pillow + numpy:  pip3 install pillow numpy")
    if not shutil.which('gs'):
        sys.exit("Ghostscript not found. Install it:  brew install ghostscript")
    if not os.path.exists(args.pdf):
        sys.exit("File not found: " + args.pdf)

    out_html = args.out or (os.path.splitext(args.pdf)[0] + ' — preview.html')
    work = tempfile.mkdtemp(prefix='prep_')
    try:
        spots = run(args.pdf, work, args.dpi)
        if not spots:
            sys.exit("No spot/separation channels found in this PDF. "
                     "This tool needs a print file with named spot finishes.")
        W = args.width
        finishes = []
        for name, path in spots.items():
            im = Image.open(path).convert('L')
            a = 255 - np.asarray(im).astype(np.float32)        # invert: finish present = white
            if a.max() < 8:                                    # empty plate
                continue
            if is_process(name) and a.max() < 40:              # near-empty process plate
                continue
            h = int(round(im.size[1] * W / im.size[0]))
            im2 = Image.fromarray((255 - a).astype('uint8')).resize((W, h), Image.LANCZOS)
            mask = (255 - np.asarray(im2).astype(np.float32))  # re-invert after resize
            png = Image.fromarray(np.clip(mask, 0, 255).astype('uint8'))
            import io
            buf = io.BytesIO(); png.save(buf, format='PNG')
            data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
            mat = classify(name); mat['img'] = data
            finishes.append(mat)

        if not finishes:
            sys.exit("All separations were empty — nothing to render.")

        # report
        print("Detected %d finish channel(s):" % len(finishes))
        for f in finishes:
            kind = ('metal' if f['metal'] else 'ink')
            sheen = 'gloss' if f['clear'] > 0.5 else ('matte' if (f['rough'] > 0.5 or f['flake']) else 'satin')
            print("  • %-26s -> %s, %s%s" % (f['name'], kind, sheen,
                                             ' +flake' if f['flake'] else ''))

        html = TEMPLATE.replace('__FINISHES__', json.dumps(finishes))
        html = html.replace('__TITLE__', os.path.basename(os.path.splitext(args.pdf)[0]))
        with open(out_html, 'w') as fh:
            fh.write(html)
        print("\nWrote:  %s  (%.0f KB)\nOpen it in your browser." %
              (out_html, os.path.getsize(out_html) / 1024))
    finally:
        shutil.rmtree(work, ignore_errors=True)

# ---------------------------------------------------------------- viewer template
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__ — Finish Preview</title>
<style>
  :root{--bg:#0c0d11;--panel:#15171e;--panel2:#1c1f28;--line:#2a2e3a;--txt:#e8eaf0;--muted:#969cab;--accent:#c8a24a;}
  *{box-sizing:border-box} html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;overflow:hidden;}
  .wrap{display:flex;height:100%;}
  .stage{flex:1;position:relative;background:radial-gradient(130% 130% at 50% 0%,#23262f 0%,#0a0b0e 70%);}
  #c{width:100%;height:100%;display:block;cursor:grab;} #c:active{cursor:grabbing;}
  .hint{position:absolute;left:50%;bottom:14px;transform:translateX(-50%);color:var(--muted);font-size:12px;
    background:rgba(0,0,0,.4);padding:6px 12px;border-radius:20px;pointer-events:none;}
  .drop{position:absolute;inset:0;display:none;align-items:center;justify-content:center;
    background:rgba(10,12,16,.85);color:#fff;font-size:18px;border:3px dashed var(--accent);z-index:5;}
  .panel{width:320px;flex:none;background:var(--panel);border-left:1px solid var(--line);padding:18px 18px 40px;overflow-y:auto;}
  h1{font-size:15px;margin:0 0 2px;} .sub{color:var(--muted);font-size:11.5px;margin:0 0 16px;line-height:1.5;}
  .group{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px 13px;margin-bottom:12px;}
  .group h2{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin:0 0 10px;font-weight:600;}
  label.row{display:flex;align-items:center;justify-content:space-between;font-size:12.5px;margin:9px 0;gap:10px;}
  input[type=range]{width:150px;accent-color:var(--accent);}
  .val{color:var(--accent);font-variant-numeric:tabular-nums;font-size:12px;min-width:46px;text-align:right;}
  .btn{background:#0e0f13;border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:8px 10px;font-size:12.5px;cursor:pointer;width:100%;}
  .btn:hover{border-color:var(--accent);} .btn.active{border-color:var(--accent);color:var(--accent);}
  .frow{display:flex;align-items:center;gap:8px;font-size:12px;margin:6px 0;}
  .chip{width:14px;height:14px;border-radius:4px;border:1px solid rgba(255,255,255,.2);flex:none;}
  .fname{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .fkind{color:var(--muted);font-size:10.5px;}
  input[type=checkbox]{accent-color:var(--accent);width:15px;height:15px;}
  .seg{display:flex;gap:6px;margin-bottom:8px;} .seg .btn{padding:7px 6px;}
  .err{position:absolute;inset:0;display:none;align-items:center;justify-content:center;color:#ff8585;font-size:14px;padding:30px;text-align:center;}
  .load{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);color:var(--muted);font-size:13px;}
  select{background:#0e0f13;color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:4px 6px;font-size:11px;}
</style></head>
<body>
<div class="wrap">
  <div class="stage">
    <canvas id="c"></canvas>
    <div class="load" id="load">Building materials & environment…</div>
    <div class="err" id="err"></div>
    <div class="drop" id="drop">Drop a photo to use as the reflection environment</div>
    <div class="hint">Drag to tilt · scroll to zoom · drop a photo of your shop to reflect it</div>
  </div>
  <div class="panel">
    <h1>__TITLE__</h1>
    <p class="sub">Physically-based finish preview. Real metal/foil reflecting a real environment. Finishes auto-detected from the print file — tweak any of them below, or drop in your own photo to reflect it.</p>
    <div class="group">
      <h2>Environment</h2>
      <div class="seg"><button class="btn active" id="envStudio">Studio</button><button class="btn" id="envLoadBtn">Load photo…</button></div>
      <input type="file" id="envFile" accept="image/*" style="display:none">
      <label class="row"><span>Exposure</span><input type="range" id="exp" min="20" max="240" value="110"><span class="val" id="expV">1.10</span></label>
      <label class="row"><span>Env brightness</span><input type="range" id="envB" min="20" max="260" value="100"><span class="val" id="envBV">1.00</span></label>
      <label class="row"><span>Show background</span><input type="checkbox" id="bgToggle"></label>
    </div>
    <div class="group">
      <h2>View</h2>
      <label class="row"><span>Auto-rotate</span><input type="checkbox" id="auto"></label>
      <button class="btn" id="reset">Reset view</button>
    </div>
    <div class="group">
      <h2>Finishes (toggle / adjust)</h2>
      <div id="finishes"></div>
    </div>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const FINISHES=__FINISHES__;
const errEl=document.getElementById('err'), loadEl=document.getElementById('load');
function fail(m){errEl.style.display='flex';errEl.textContent=m;loadEl.style.display='none';}
if(typeof THREE==='undefined'){fail('Could not load three.js from the CDN. Check your connection and reopen.');}

let renderer,scene,camera,mesh,material,pmrem,studioEnv,photoEnv=null;
let maps={}, enabled=FINISHES.map(()=>1);
let W=0,H=0,redCh=[];
const NF=FINISHES.length;

function loadAll(){ let done=0; const els=[];
  FINISHES.forEach((f,i)=>{ const im=new Image();
    im.onload=()=>{els[i]=im; if(++done===NF){W=els[0].naturalWidth;H=els[0].naturalHeight;extract(els);start();}};
    im.onerror=()=>fail('Could not load a finish mask'); im.src=f.img; }); }
function extract(els){ const cv=document.createElement('canvas');cv.width=W;cv.height=H;const cx=cv.getContext('2d');
  for(let i=0;i<NF;i++){ cx.setTransform(1,0,0,1,0,0);cx.clearRect(0,0,W,H);
    cx.translate(0,H);cx.scale(1,-1);cx.drawImage(els[i],0,0,W,H);cx.setTransform(1,0,0,1,0,0);
    const d=cx.getImageData(0,0,W,H).data;const r=new Uint8Array(W*H);
    for(let p=0;p<W*H;p++)r[p]=d[p*4];redCh[i]=r; } }

function buildMaps(){ const N=W*H;
  const alb=new Uint8ClampedArray(N*4),orm=new Uint8ClampedArray(N*4),alpha=new Uint8ClampedArray(N*4),nrm=new Uint8ClampedArray(N*4);
  for(let p=0;p<N;p++){ let best=-1,bv=0,shape=0;
    for(let i=0;i<NF;i++){const raw=redCh[i][p]; if(raw>shape)shape=raw; const v=raw*enabled[i]; if(v>bv){bv=v;best=i;}}
    const o=p*4; alpha[o]=alpha[o+1]=alpha[o+2]=shape;alpha[o+3]=255;
    nrm[o]=128;nrm[o+1]=128;nrm[o+2]=255;nrm[o+3]=255;
    if(best<0||bv<40){ alb[o]=12;alb[o+1]=12;alb[o+2]=14;alb[o+3]=255; orm[o]=0;orm[o+1]=153;orm[o+2]=0;orm[o+3]=255; continue; }
    const f=FINISHES[best];
    alb[o]=Math.round(Math.pow(f.col[0],1/2.2)*255);alb[o+1]=Math.round(Math.pow(f.col[1],1/2.2)*255);alb[o+2]=Math.round(Math.pow(f.col[2],1/2.2)*255);alb[o+3]=255;
    orm[o]=Math.round(f.clear*255);orm[o+1]=Math.round(f.rough*255);orm[o+2]=Math.round(f.metal*255);orm[o+3]=255;
    if(f.flake){const h=hash(p),h2=hash(p*1.7+11);nrm[o]=Math.round(128+(h-0.5)*120);nrm[o+1]=Math.round(128+(h2-0.5)*120);}
  }
  function mk(arr,enc,nearest){const t=new THREE.DataTexture(arr,W,H,THREE.RGBAFormat);t.needsUpdate=true;
    t.wrapS=t.wrapT=THREE.ClampToEdgeWrapping;const fl=nearest?THREE.NearestFilter:THREE.LinearFilter;
    t.minFilter=fl;t.magFilter=fl;t.generateMipmaps=false;t.anisotropy=renderer?renderer.capabilities.getMaxAnisotropy():1;
    if(enc)t.encoding=enc;return t;}
  maps.albedo=mk(alb,THREE.sRGBEncoding,false);maps.orm=mk(orm,null,true);maps.alpha=mk(alpha,null,false);maps.normal=mk(nrm,null,true);
}
function hash(n){const s=Math.sin(n*12.9898)*43758.5453;return s-Math.floor(s);}

function makeStudioEnv(){const cv=document.createElement('canvas');cv.width=1024;cv.height=512;const x=cv.getContext('2d');
  let g=x.createLinearGradient(0,0,0,512);g.addColorStop(0,'#3a3f49');g.addColorStop(0.42,'#0f1115');g.addColorStop(0.62,'#0a0c10');g.addColorStop(1,'#16181d');
  x.fillStyle=g;x.fillRect(0,0,1024,512);x.globalCompositeOperation='lighter';
  function box(cx,cy,w,h,a){const rg=x.createRadialGradient(cx,cy,0,cx,cy,Math.max(w,h));rg.addColorStop(0,'rgba(255,255,255,'+a+')');rg.addColorStop(1,'rgba(255,255,255,0)');x.fillStyle=rg;x.fillRect(cx-w,cy-h,w*2,h*2);}
  box(320,120,240,90,0.95);box(720,140,220,80,0.8);box(520,70,300,60,0.7);box(160,300,120,160,0.18);box(880,320,140,180,0.16);
  x.globalCompositeOperation='source-over';
  const t=new THREE.CanvasTexture(cv);t.mapping=THREE.EquirectangularReflectionMapping;t.encoding=THREE.sRGBEncoding;return t;}

let baseCamZ=4.4;
function start(){const canvas=document.getElementById('c');
  renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});
  renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));
  renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.10;
  scene=new THREE.Scene();scene.background=null;
  camera=new THREE.PerspectiveCamera(26,1,0.1,100);camera.position.set(0,0,baseCamZ);
  pmrem=new THREE.PMREMGenerator(renderer);pmrem.compileEquirectangularShader();
  const eq=makeStudioEnv();studioEnv=pmrem.fromEquirectangular(eq).texture;eq.dispose();scene.environment=studioEnv;
  var _k=new THREE.DirectionalLight(0xffffff,0.45);_k.position.set(-1.2,1.4,2.0);scene.add(_k);
  var _f=new THREE.DirectionalLight(0xbfd0ff,0.18);_f.position.set(1.5,-0.6,1.0);scene.add(_f);
  buildMaps();
  const aspect=W/H,ph=2.0,pw=ph*aspect;const geo=new THREE.PlaneGeometry(pw,ph,1,1);
  material=new THREE.MeshPhysicalMaterial({map:maps.albedo,metalnessMap:maps.orm,roughnessMap:maps.orm,clearcoatMap:maps.orm,
    metalness:1.0,roughness:1.0,clearcoat:1.0,clearcoatRoughness:0.06,normalMap:maps.normal,normalScale:new THREE.Vector2(0.6,0.6),
    alphaMap:maps.alpha,transparent:true,alphaTest:0.35,envMapIntensity:1.0});
  const front=new THREE.Mesh(geo,material);
  const backMat=new THREE.MeshPhysicalMaterial({color:0x050507,roughness:0.5,metalness:0.0,clearcoat:0.25,clearcoatRoughness:0.4,alphaMap:maps.alpha,transparent:true,alphaTest:0.35});
  const back=new THREE.Mesh(geo,backMat);back.rotation.y=Math.PI;
  mesh=new THREE.Group();mesh.add(front);mesh.add(back);scene.add(mesh);
  resize();window.addEventListener('resize',resize);loadEl.style.display='none';wireUI();animate();
}
function resize(){const s=document.querySelector('.stage');renderer.setSize(s.clientWidth,s.clientHeight,false);camera.aspect=s.clientWidth/s.clientHeight;camera.updateProjectionMatrix();}

let tilt={x:0,y:0},target={x:0,y:0},dragging=false,last={x:0,y:0},autorot=false,zoom=1;
function animate(){requestAnimationFrame(animate);
  if(autorot)target.y+=0.004;tilt.x+=(target.x-tilt.x)*0.08;tilt.y+=(target.y-tilt.y)*0.08;
  if(mesh){mesh.rotation.x=tilt.x;mesh.rotation.y=tilt.y;}camera.position.z=baseCamZ*zoom;renderer.render(scene,camera);}

function wireUI(){const canvas=document.getElementById('c');
  canvas.addEventListener('pointerdown',e=>{dragging=true;last={x:e.clientX,y:e.clientY};});
  window.addEventListener('pointerup',()=>dragging=false);
  window.addEventListener('pointermove',e=>{if(!dragging)return;target.y+=(e.clientX-last.x)*0.006;target.x+=(e.clientY-last.y)*0.006;target.x=Math.max(-0.7,Math.min(0.7,target.x));last={x:e.clientX,y:e.clientY};});
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom*=(1+Math.sign(e.deltaY)*0.08);zoom=Math.max(0.5,Math.min(2.2,zoom));},{passive:false});
  const $=id=>document.getElementById(id);
  $('exp').oninput=e=>{renderer.toneMappingExposure=e.target.value/100;$('expV').textContent=(e.target.value/100).toFixed(2);};
  $('envB').oninput=e=>{material.envMapIntensity=e.target.value/100;$('envBV').textContent=(e.target.value/100).toFixed(2);};
  $('auto').onchange=e=>autorot=e.target.checked;
  $('bgToggle').onchange=e=>{scene.background=e.target.checked?(photoEnv||studioEnv):null;};
  $('reset').onclick=()=>{target={x:0,y:0};zoom=1;autorot=false;$('auto').checked=false;};
  $('envStudio').onclick=()=>{scene.environment=studioEnv;if($('bgToggle').checked)scene.background=studioEnv;setEnvBtn('envStudio');};
  $('envLoadBtn').onclick=()=>$('envFile').click();
  $('envFile').onchange=e=>{const f=e.target.files[0];if(f)loadEnvImage(URL.createObjectURL(f));};
  const fw=$('finishes');
  FINISHES.forEach((f,i)=>{const kind=(f.metal?'metal':'ink')+' · '+(f.clear>0.5?'gloss':(f.rough>0.5?'matte':'satin'));
    const row=document.createElement('div');row.className='frow';
    row.innerHTML='<input type="checkbox" checked><span class="chip" style="background:'+f.chip+'"></span><span class="fname">'+f.name+'<br><span class="fkind">'+kind+'</span></span>'+
      '<select data-i="'+i+'"><option value="auto">auto</option><option value="gloss">gloss</option><option value="matte">matte</option><option value="mirror">mirror</option></select>';
    row.querySelector('input').onchange=ev=>{enabled[i]=ev.target.checked?1:0;rebuild();};
    row.querySelector('select').onchange=ev=>{applyOverride(i,ev.target.value);rebuild();};
    fw.appendChild(row);});
  const stage=document.querySelector('.stage'),drop=$('drop');
  stage.addEventListener('dragover',e=>{e.preventDefault();drop.style.display='flex';});
  stage.addEventListener('dragleave',()=>{drop.style.display='none';});
  stage.addEventListener('drop',e=>{e.preventDefault();drop.style.display='none';const f=e.dataTransfer.files[0];if(f&&f.type.startsWith('image'))loadEnvImage(URL.createObjectURL(f));});
}
function applyOverride(i,v){const f=FINISHES[i];
  if(v==='gloss'){f.rough=f.metal?0.06:0.10;f.clear=1.0;f.flake=0;}
  else if(v==='matte'){f.rough=f.metal?0.40:0.80;f.clear=0.0;f.flake=f.metal?1:0;}
  else if(v==='mirror'){f.rough=0.02;f.clear=1.0;f.flake=0;f.metal=1;}}
function setEnvBtn(id){['envStudio','envLoadBtn'].forEach(b=>document.getElementById(b).classList.toggle('active',b===id));}
function loadEnvImage(url){const ldr=new THREE.TextureLoader();ldr.load(url,tex=>{tex.mapping=THREE.EquirectangularReflectionMapping;tex.encoding=THREE.sRGBEncoding;
  photoEnv=pmrem.fromEquirectangular(tex).texture;tex.dispose();scene.environment=photoEnv;if(document.getElementById('bgToggle').checked)scene.background=photoEnv;setEnvBtn('envLoadBtn');});}
function rebuild(){buildMaps();material.map=maps.albedo;material.metalnessMap=maps.orm;material.roughnessMap=maps.orm;material.clearcoatMap=maps.orm;material.normalMap=maps.normal;material.alphaMap=maps.alpha;material.needsUpdate=true;}
loadAll();
</script></body></html>"""

if __name__ == '__main__':
    main()
