// 预检在与成片相同的浏览器页面运行，依据画师标定的地面、通行带和对象尺寸。
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const root=path.resolve(process.argv[2]||'.'), dir=path.join(root,'build/stage-audit');
const planFile=path.join(root,'page/blocking.json'), plan=JSON.parse(fs.readFileSync(planFile));
const sha=createHash('sha256');
function walk(d){for(const n of fs.readdirSync(d).sort()){const p=path.join(d,n);if(fs.statSync(p).isDirectory())walk(p);else{sha.update(path.relative(root,p));sha.update(fs.readFileSync(p))}}}
for(const n of ['page','lib','assets/bg','assets/cut','assets/host','assets/fonts']){const p=path.join(root,n);if(fs.existsSync(p)){if(n==='page'){for(const f of fs.readdirSync(p).sort())if(fs.statSync(path.join(p,f)).isFile()){sha.update(f);sha.update(fs.readFileSync(path.join(p,f)))}}else walk(p)}}
const digest=sha.digest('hex'), report=path.join(dir,'result.json'), sign=path.join(dir,'review.json');
if(process.argv.includes('--check')){
 const ok=JSON.parse(fs.readFileSync(report)), rev=JSON.parse(fs.readFileSync(sign));
 if(!fs.existsSync(path.join(dir,'motion.mp4'))||ok.digest!==digest||rev.digest!==digest||!ok.samples||Object.keys(plan.shots).some(s=>['route','scale','camera'].some(key=>!rev.shots?.[s]?.[key]?.trim()))) throw Error('镜头或素材已变更，或逐镜视觉复核不完整。重新预检并复核。');
 for(const [id,sc] of Object.entries(plan.shots)){
  const checks=sc.limbChecks||[];
  if(Object.keys(sc.routes||{}).length && !checks.length)throw Error(id+' 需要连续动作肢体检查');
  for(const [j,c] of checks.entries()){
   const folder=path.join(dir,id+'-limbs-'+j);
   if(!rev.shots[id].limbs?.[j]?.trim()||!fs.existsSync(folder)||fs.readdirSync(folder).filter(f=>f.endsWith('.png')).length!==Math.ceil((c.end-c.start)*30)+1)throw Error(id+' 缺少逐帧肢体复核：'+c.name)
  }
 }
 console.log(digest);process.exit(0);
}
fs.mkdirSync(dir,{recursive:true});
const lock=path.join(dir,'audit.lock');
if(fs.existsSync(lock)){
 const pid=Number(fs.readFileSync(lock,'utf8'));
 try{process.kill(pid,0);throw Error('已有镜头预检运行中')}catch(e){if(e.code!=='ESRCH')throw e;fs.unlinkSync(lock)}
}
fs.writeFileSync(lock,String(process.pid),{flag:'wx'});
process.on('exit',()=>fs.rmSync(lock,{force:true}));
fs.rmSync(report,{force:true});
const sk=path.dirname(fileURLToPath(import.meta.url));
const python=path.join(process.env.HOME,'.venvs/vocab-story/bin/python');
execFileSync(fs.existsSync(python)?python:'python3',['-c',
  "from PIL import Image;from native_alpha import check_alpha;import sys,pathlib;[check_alpha(Image.open(p),str(p),trimmed=True) for p in pathlib.Path(sys.argv[1]).glob('*.png')]",
  path.join(root,'assets/cut')],{cwd:sk,stdio:'inherit'});
const pw=createRequire(path.join(root,'package.json'))('playwright');
const browser=await pw.chromium.launch({args:['--allow-file-access-from-files']});
try{
 const page=await browser.newPage({viewport:{width:plan.width,height:plan.height}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'page/index.html')).href);await page.evaluate(()=>window.__ready);await page.evaluate(()=>document.fonts.ready);
 const actual=await page.evaluate(()=>Object.keys(L));if(actual.sort().join()!==Object.keys(plan.shots).sort().join()) throw Error('所有镜头都需要校正记录');
 let samples=0;
 for(const [id,sc] of Object.entries(plan.shots)){
  if(!sc.camera||!sc.ground||!sc.surface||!sc.action)throw Error(id+' 需要机位、地面、通行带和动作说明');
  const loc=await page.evaluate(id=>({start:videoOf(L[id].start),end:videoOf(L[id].end)}),id);
  for(const [name,r] of Object.entries(sc.routes||{})){
   if(r.points.length<2||!r.facing||!r.view)throw Error(id+'/'+name+' 路径缺少朝向或节点');
   for(let j=1;j<r.points.length;j++){const a=r.points[j-1],b=r.points[j];if(b[0]<=a[0] || (r.view==='side'&&Math.abs(b[2]-a[2])>Math.abs(b[1]-a[1])*.35))throw Error(id+'/'+name+' 路线与素材视角不符，请换素材或调整机位')}
  }
  const times=new Set([loc.start+.04,(loc.start+loc.end)/2,loc.end-.045,...Object.values(sc.routes||{}).flatMap(r=>r.points.map(p=>Math.min(loc.end-.01,Math.max(loc.start+.01,p[0]))))]);
  for(let t=loc.start+.1;t<loc.end;t+=.2)times.add(t);
  for(const t of [...times].sort((a,b)=>a-b)){
   const issues=await page.evaluate(({id,t,sc,plan})=>{
    window.__seek(t);const l=L[id],err=[];const cam=new DOMMatrix(getComputedStyle(l.cam).transform);
    const visibleKeys=Object.entries(l.spr).filter(([,im])=>im.style.display!=='none').map(([key])=>key);
    const previous=l._auditVisible||[];
    if(previous.some(k=>!visibleKeys.includes(k)) && visibleKeys.some(k=>!previous.includes(k)) && !sc.limbChecks?.length)
      err.push('画面出现姿势切换，须标注切换前后的局部连续帧');
    l._auditVisible=visibleKeys;
    const box=l.cam.getBoundingClientRect();
    const prev=l._auditCamera, dt=prev?t-prev.t:0;
    if(dt>0.001 && dt<=.21 && !sc.camera.cuts?.some(c=>c>=prev.t && c<=t)){
      const pan=Math.hypot(cam.e-prev.x,cam.f-prev.y)/dt;
      if(pan>(sc.camera.maxPan??innerWidth*4)||Math.abs(cam.a-prev.z)/dt>(sc.camera.maxZoomRate??4))err.push('同一镜头内相机突跳，请调整缓动或标明切点')
    }
    l._auditCamera={t,x:cam.e,y:cam.f,z:cam.a};
    if(!Number.isFinite(cam.a)||cam.a<sc.camera.zoom[0]-.005||cam.a>sc.camera.zoom[1]+.005||box.left>1||box.top>1||box.right<innerWidth-1||box.bottom<innerHeight-1)err.push('运镜露边或超出标定倍率');
    for(const [k,im] of Object.entries(l.spr)){if(im.style.display==='none')continue;
     const p=im._stagePose;if(!p) {err.push(k+' 未接入脚点与比例校正');continue}
     const [hz,u,foot]=sc.ground,ratio=sc.sizes?.[k]??plan.sizes[k],expected=u*(p.y-hz)/(foot-hz)*ratio;
     if(!Number.isFinite(expected)||Math.abs(parseFloat(im.style.height)-expected)>1)err.push(k+' 实际显示高度异常');
     if(!sc.routes?.[k]){
       const anchors=(l._auditAnchors??={}), a=(anchors[k]??={x:p.x,y:p.y});
       if(!sc.gestures?.[k] && Math.hypot(p.x-a.x,p.y-a.y)>expected*.65)err.push(k+' 大幅位移缺少路径；行走请标路线，局部表演请标 gestures')
     }
     const band=sc.surfaces?.[k]??sc.surface;
     if(p.y<band[0]-1||p.y>band[1]+1)err.push(k+' 脚点偏离可通行范围');
     const poly=sc.corridors?.[k]??sc.corridor;
     if(poly){let inside=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){
       const [x,y]=poly[i],[x0,y0]=poly[j];
       if((y>p.y)!==(y0>p.y)&&p.x<(x0-x)*(p.y-y)/(y0-y)+x)inside=!inside;
     }if(!inside)err.push(k+' 脚点离开标定路面多边形')}
     if(sc.routes?.[k]){const q=stagePlacement(plan,id,k,t,p);if(Math.hypot(p.x-q.x,p.y-q.y)>1||Boolean(p.flip)!==Boolean(q.flip))err.push(k+' 路径或朝向偏离')}
    }return err;
   },{id,t,sc,plan});if(issues.length)throw Error(id+' '+t.toFixed(2)+'s '+issues.join('；'));samples++;
  }
  const checks=sc.limbChecks||[];
  if(Object.keys(sc.routes||{}).length && !checks.length)throw Error(id+' 需要标注步态或动作切换的局部连续帧');
  for(const [j,c] of checks.entries()){
   if(!(c.start>=loc.start && c.end<=loc.end && c.end>c.start && c.crop?.length===4))throw Error(id+' 肢体采样区间或裁区无效');
   const [x,y,width,height]=c.crop,folder=path.join(dir,id+'-limbs-'+j);
   fs.mkdirSync(folder,{recursive:true});
   for(const old of fs.readdirSync(folder).filter(f=>/^frame-\d+\.png$/.test(f)))fs.unlinkSync(path.join(folder,old));
   for(let i=0;i<=Math.ceil((c.end-c.start)*30);i++){
    await page.evaluate(t=>window.__seek(t),Math.min(c.end,c.start+i/30));
    await page.screenshot({path:path.join(folder,'frame-'+String(i).padStart(4,'0')+'.png'),clip:{x,y,width,height}});
   }
  }
  for(const [j,k] of [.13,.50,.87].entries()){let t=loc.start+(loc.end-loc.start)*k;await page.evaluate(t=>window.__seek(t),t);await page.screenshot({path:path.join(dir,id+'-'+j+'.jpg'),type:'jpeg',quality:82})}
 }
 if(errors.length)throw Error(errors.join('\n'));
 execFileSync(process.execPath,[path.join(sk,'motion_preview.mjs'),root],{stdio:'inherit'});
 fs.writeFileSync(report,JSON.stringify({digest,samples,shots:actual},null,2));console.log(samples+' 个时刻已检查；逐镜复核三帧和有运动的连续片段后填写 review.json。');
}finally{await browser.close()}
