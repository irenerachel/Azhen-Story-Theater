import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import path from 'node:path';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const root=path.resolve(process.argv[2]), dir=path.join(root,'build/stage-audit'),plan=JSON.parse(fs.readFileSync(path.join(root,'page/blocking.json')));
const pw=createRequire(path.join(root,'package.json'))('playwright');
const browser=await pw.chromium.launch({args:['--allow-file-access-from-files']});
try{
 const page=await browser.newPage({viewport:{width:plan.width,height:plan.height},deviceScaleFactor:.4});
 await page.goto(pathToFileURL(path.join(root,'page/index.html')).href);
 await page.evaluate(()=>window.__ready);await page.evaluate(()=>document.fonts.ready);
 const duration=await page.evaluate(()=>window.__scene.duration),fps=10;
 const tmp=path.join(dir,'motion-'+process.pid+'.mp4');
 const ff=spawn('ffmpeg',['-v','error','-y','-f','image2pipe','-vcodec','mjpeg','-framerate',String(fps),'-i','-','-c:v','libx264','-pix_fmt','yuv420p',tmp],{stdio:['pipe','ignore','inherit']});
 const done=once(ff,'close');
 for(let i=0;i<duration*fps;i++){await page.evaluate(t=>window.__seek(t),i/fps);if(!ff.stdin.write(await page.screenshot({type:'jpeg',quality:75})))await once(ff.stdin,'drain')}
 ff.stdin.end();if((await done)[0]!==0)throw Error('动态预览失败');
 fs.renameSync(tmp,path.join(dir,'motion.mp4'));
}finally{await browser.close()}
