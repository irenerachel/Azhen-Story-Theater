// 镜头单位为设计画布像素。路径点是脚底或车轮接地的位置。
function stagePlacement(plan, shot, sprite, t, pose) {
  const scene = plan.shots[shot];
  if (!scene) throw Error('缺少镜头校正：'+shot);
  const route = scene.routes?.[sprite];
  const out = {...pose};
  if (route) {
    const pts = route.points;
    const j = pts.findIndex(p=>p[0]>=t);
    const end = j<0 ? pts.length-1 : Math.max(1,j);
    const [a,b]=[pts[end-1],pts[end]];
    const k=Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0])));
    out.x=a[1]+(b[1]-a[1])*k;
    out.y=a[2]+(b[2]-a[2])*k;
    if (route.view==='side' && b[1]!==a[1]) out.flip=(b[1]>a[1]) !== (route.facing==='right');
  }
  const [horizon,unit,foot]=scene.ground;
  const ratio=scene.sizes?.[sprite]??plan.sizes[sprite];
  if (!(ratio>0 && unit>0 && foot>horizon && out.y>horizon)) throw Error(shot+'/'+sprite+' 缺少有效比例或地面标定');
  out.h=unit*(out.y-horizon)/(foot-horizon)*ratio;
  return out;
}

window.stagePlanReady=fetch(new URL('blocking.json',document.baseURI))
 .then(r=>{if(!r.ok)throw Error('请先标定 page/blocking.json');return r.json()})
 .then(plan=>{window.stagePlan=plan});
