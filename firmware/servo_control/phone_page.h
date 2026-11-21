#pragma once
// Self-contained page: works without mobile data, CDN, or Internet access.
const char PHONE_PAGE[] PROGMEM = R"ROBOTPAGE(<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#12232b"><link rel="icon" href="data:,"><title>四足机器人 · 控制台</title>
<style>
:root{color-scheme:light;--ink:#19313b;--muted:#617780;--line:#dbe4e6;--green:#087f70;--red:#bc3447}
*{box-sizing:border-box}body{margin:0;background:#eef3f3;color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Microsoft YaHei",sans-serif}
header{background:#12232b;color:white;padding:28px max(18px,calc((100% - 940px)/2)) 62px}header small{color:#94c9bf;letter-spacing:.12em}h1{font-size:27px;margin:6px 0}header p{margin:0;color:#b5c7cd}
main{max-width:976px;margin:-34px auto 100px;padding:0 18px}section{background:white;border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:16px;box-shadow:0 5px 20px #12232b05}h2{font-size:18px;margin:0 0 12px}h3{font-size:16px;margin:0 0 12px}.muted,small{color:var(--muted)}p{margin:8px 0}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.card{border:1px solid var(--line);border-radius:12px;padding:15px;min-width:0}.wide{grid-column:1/-1}
label{display:block;font-size:13px;color:var(--muted)}input,select{display:block;width:100%;min-width:0;margin:5px 0 8px;border:1px solid #bbcdd1;border-radius:8px;background:#fff;color:var(--ink);font:inherit;padding:10px}input[type=range]{padding:0;accent-color:var(--green)}button{border:0;border-radius:9px;padding:12px 16px;font:600 14px system-ui;background:#e6efef;color:var(--ink);cursor:pointer;min-height:44px}button:disabled{opacity:.45;cursor:wait}button.primary{background:var(--green);color:white}button.danger{background:var(--red);color:white}button.outline{border:1px solid var(--line);background:white}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #4db4a5;outline-offset:2px}.badge{border-radius:20px;padding:4px 10px;background:#e6f4ef;color:#176352;font-size:13px}.badge.off{background:#fcebed;color:var(--red)}#notice{min-height:26px;overflow-wrap:anywhere}.error{color:var(--red)}.note{border-left:3px solid #e3b35d;padding-left:12px;font-size:13px;color:#6d674f}details summary{cursor:pointer;font-weight:600}details[open] summary{margin-bottom:14px}.dock{position:fixed;bottom:0;left:0;right:0;background:#f7fafaf2;border-top:1px solid var(--line);padding:12px 18px calc(12px + env(safe-area-inset-bottom));display:flex;justify-content:center;gap:12px;backdrop-filter:blur(8px);z-index:10}.dock button{max-width:430px;flex:1}.live{font-variant-numeric:tabular-nums}.leg-actions{margin-top:10px}.help{font-size:13px;color:var(--muted)}
@media(max-width:580px){.grid{grid-template-columns:1fr}section{padding:16px}header{padding-top:22px}main{padding:0 12px}.row>*{flex:1}h1{font-size:24px}.card .row{gap:6px}}
</style></head><body>
<header><small>PKU · 第3组 / R3</small><h1>四足机器人控制台</h1><p>手机调角 · 标定 · 前进后退与转向</p></header>
<main>
<section><div class="row"><h2 style="margin:0;flex:1">运行状态</h2><span id="connection" class="badge off">连接中</span><span id="motion" class="badge">—</span></div>
<p id="summary" class="muted live">等待读取机器人状态…</p><div id="notice" role="status" aria-live="polite">页面加载不会让机器人运动。</div>
<p class="note">角度均为命令值，无传感器反馈。停止保持最后姿态，不会自动落脚或断电；再次启动默认前进直行。手机心跳中断约2.5秒后停止；软件超时受网络处理延迟影响。</p></section>
<section><h2>运动与速度</h2><div class="fields"><label>速度倍率（直接输入小数）<input id="speed" type="number" min="0.05" max="4" step="any" value="1" inputmode="decimal"></label><div><label>当前实际设置</label><p id="speedActual" class="live">—</p><button id="applySpeed" class="primary">应用速度</button></div></div>
<p class="help">倍率0.05～4；周期 = 4秒 ÷ 倍率。可输入0.73等任意数值，不是固定档位。仅调整轨迹播放速率，重启回到1倍。</p>
<div class="row"><button id="back">后退</button><button id="left">左转</button><button id="right">右转</button><button id="straight" class="outline">回直行</button></div>
<p class="help">左转/右转是带差速的弧线；行走中可直接切换，固件会平滑过渡。“回直行”保持当前前进/后退方向并取消转向；底部“开始前行”回前进直行。</p>
<div class="fields"><label>转弯差速增益（0～0.8）<input id="turnGain" type="number" min="0" max="0.8" step="any" value="0.5" inputmode="decimal"></label><div><p id="turnGainActual" class="live">—</p><button id="applyTurn">应用转弯增益</button></div></div>
<p class="help">只影响左右转时左右腿的步长差；停止时可改，重启回0.5。增益越大转得越急，但可能超出可达范围。</p>
<div class="fields"><label>末端前后偏移 mm（负=向后）<input id="footOffset" type="number" min="-20" max="20" step="any" value="0" inputmode="decimal"></label><div><p id="footOffsetActual" class="live">—</p><button id="applyOffset">应用末端偏移</button></div></div>
<p class="help">同时作用于回站姿和行走轨迹；负值足端后移，正值前移。前脚吃重用正值、后脚吃重用负值，1mm步进。停止时可改，仅RAM；确认后用 stand record + stand save 固化新站姿。</p>
<div class="fields"><label>步态中心 mm（负=足端后移，仅walk）<input id="walkCenter" type="number" min="-25" max="25" step="any" value="0" inputmode="decimal"></label><div><p id="walkCenterActual" class="live">—</p><button id="applyCenter">应用步态中心</button></div></div>
<p class="help">只改行走轨迹的前后中心，不动站姿；负值把步态足端整体后移，用于后腿前旋过多/抬对侧前脚时后仰。停止时可改；walk save 保存。</p>
<div class="fields"><label>直行偏置（正=左偏，抵消右漂）<input id="walkBias" type="number" min="-0.4" max="0.4" step="any" value="0" inputmode="decimal"></label><div><p id="walkBiasActual" class="live">—</p><button id="applyBias">应用直行偏置</button></div></div>
<p class="help">只在直行时生效，左右转不受影响。例如 0.09 等价于 walk turn 0.09 + walk left 的小左偏；停止时可改，walk save 保存。</p>
<div class="row"><button id="wave">打招呼</button><select id="waveLeg" aria-label="打招呼腿"><option value="1">左前腿</option><option value="2">右前腿</option><option value="3">左后腿</option><option value="4">右后腿</option></select><button id="applyWaveLeg" class="outline">选择打招呼腿</button></div>
<p class="help">默认左前腿，抬约20mm后摆动3次；三条支撑腿前移并把重心偏右后，后腿抬25mm更稳。前腿抬起仍会有俯仰，第一次请托住。打招呼中可点停止取消。</p>
<div class="fields"><label>行走输出死区（命令角 °）<input id="deadband" type="number" min="0" max="5" step="any" value="1" inputmode="decimal"></label><div><p id="deadbandActual" class="live">—</p><button id="applyDeadband">应用死区</button></div></div>
<p class="help">行走时，角度变化积累到该阈值才更新舵机命令。0关闭死区，重启恢复1°。</p>
<div class="row"><button id="stand">回当前标定站姿</button><button id="refresh" class="outline">重新读取参数</button></div></section>
<section><h2>步态参数</h2><p class="help">先停止，再应用。落脚深度以65mm为基准，正值向下伸，负值回缩；在该腿支撑阶段维持。stand不受影响。抬脚高度相对该腿落脚平面；时间比例按该腿摆动时长计算，摆动时长为2秒 ÷ 倍率。</p>
<div class="grid" id="legs"></div><div class="row leg-actions"><button id="gaitSave" class="primary">保存已应用的步态</button><button id="gaitLoad">载入已保存的步态</button><button id="gaitReset" class="outline">恢复默认值</button></div>
<p class="help">调参时先逐腿应用，满意后再保存。恢复默认值只更新当前步态。速度倍率重启后回到1倍。</p></section>
<section><details><summary>站姿标定与手动调角</summary><p class="note">手动调角会停止步态。修改方向前先停止。先托起机身，小幅调整；0～180只是输入范围，不是机械安全范围。滑条仅选值，点击发送后才运动。</p><div class="grid" id="servos"></div>
<div class="fields" style="margin-top:16px"><label>所有舵机命令角<input id="allAngle" type="number" min="0" max="180" step="1" value="90"></label><div class="row"><button id="allSet">全部发送</button><button id="init">全部回90°</button></div></div></details></section>
<section><h2>标定存档</h2><p class="help">先手动摆好65mm参考站姿并设置各关节方向，再记录站姿。保存会把站姿和方向写入闪存，并作为下次开机的初始姿势。载入只更新标定，需要移动时另点回当前标定站姿。</p><div class="row"><button id="capture">记录站姿到当前标定</button><button id="saveCal" class="primary">保存站姿与方向</button><button id="loadCal">载入已保存的站姿与方向</button></div><p id="calState" class="live muted">—</p></section>
<section><details><summary>Wi-Fi与手机连接</summary><p id="network" class="help">—</p><p class="help">同一路由器下可访问局域网IP或 http://quadruped.local 。也可直连机器人热点访问 http://192.168.4.1 。热点默认密码 quadrobot。手机可能提示“无互联网”，请保持连接。</p><form id="wifiForm"><label>路由器Wi-Fi名称<input id="ssid" maxlength="32" autocomplete="off" required></label><label>Wi-Fi密码<input id="password" type="password" maxlength="63" autocomplete="new-password"></label><button class="primary" type="submit">保存并连接Wi-Fi</button></form><p class="help">仅停止时可更改；保存在板内。连接失败时热点仍可用，不会阻塞串口和步态循环。</p></details></section>
<section><details><summary>串口等价命令与帮助</summary><p class="help">全部现有功能均可在上方操作，也可输入原串口命令。已有前进、后退、左转、右转；仍无姿态反馈或自动避障。</p><form id="commandForm"><label>命令<input id="command" maxlength="95" placeholder="例如：set 1 92 或 walk speed 0.73" autocomplete="off" required></label><button type="submit">发送命令</button></form></details></section>
</main><div class="dock"><button id="forward" class="primary">开始前行</button><button id="stop" class="danger">停止 · 保持姿态</button></div>
<script>
'use strict';
const $=id=>document.getElementById(id), names=['左前','右前','左后','右后'], motionText={forward:'前行中',back:'后退中',left:'左转中',right:'右转中',wave:'打招呼',stopped:'已停止'};
const client=(crypto.getRandomValues(new Uint32Array(3))).join('-');
let key='',state=null,own=false,busy=false,ticking=false,initialized=false,stopRequested=false;
let backgroundRequest=null,stopInProgress=null;
const legFields=[['lift','抬脚高度 mm',0,30,15],['depth','落脚深度修正 mm',-10,10,0],['stride','步长 mm',0,50,28],['liftPercent','抬脚时间 %',10,45,25],['lowerPercent','放脚时间 %',10,45,25]];
$('legs').innerHTML=names.map((n,i)=>`<div class="card"><h3>${i+1} · ${n}腿</h3><div class="fields">${legFields.map(([k,label,min,max,val])=>`<label>${label}<input id="leg${i}-${k}" type="number" min="${min}" max="${max}" step="any" value="${val}" inputmode="decimal"></label>`).join('')}</div><button data-leg="${i}" class="primary">应用${n}腿</button><p class="help live" id="leg${i}-actual">—</p></div>`).join('');
$('servos').innerHTML=Array.from({length:8},(_,i)=>`<div class="card"><h3>${i+1} · ${names[Math.floor(i/2)]}${i%2?'膝':'髋'}</h3><p id="servo${i}-actual" class="help live">—</p><label>命令角 °<input id="servo${i}-angle" type="number" min="0" max="180" step="1" value="90"></label><input id="servo${i}-slider" type="range" min="0" max="180" value="90" aria-label="第${i+1}路命令角"><div class="row"><button data-servo="${i}" class="primary">发送角度</button><select id="servo${i}-dir" aria-label="第${i+1}路方向"><option value="0">未设置</option><option value="1">dir +1</option><option value="-1">dir -1</option></select><button data-dir="${i}">应用方向</button></div></div>`).join('');
for(let i=0;i<8;i++){$(`servo${i}-slider`).oninput=e=>$(`servo${i}-angle`).value=e.target.value;$(`servo${i}-angle`).oninput=e=>$(`servo${i}-slider`).value=e.target.value;}
function note(text,error=false){$('notice').textContent=text;$('notice').className=error?'error':'';}
function value(id){const el=$(id);if(!el.value.trim()||!el.checkValidity())throw Error('请检查输入范围：'+id);const n=Number(el.value);if(!Number.isFinite(n))throw Error('请输入有效数字');return n;}
async function request(path,options,timeout,background=false){
  const controller=new AbortController();
  if(background)backgroundRequest=controller;
  let expired=false;
  const timer=setTimeout(()=>{expired=true;controller.abort();},timeout);
  try{
    const response=await fetch(path,{...options,signal:controller.signal});
    return {response,data:await response.json()};
  }catch(error){
    if(expired)throw Error('等待机器人响应超时');
    throw error;
  }finally{
    clearTimeout(timer);
    if(backgroundRequest===controller)backgroundRequest=null;
  }
}
async function post(path,data,background=false){
  if(!key)throw Error('尚未连接机器人');
  const {response,data:result}=await request(path,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded','X-Control-Key':key},body:new URLSearchParams({...data,client})},3000,background);
  if(!response.ok||!result.ok)throw Error(result.message||'请求失败');
  return result;
}
function syncInputs(s,scope=true){if(scope===true || scope==="all") {$('speed').value=s.speed;$('deadband').value=s.deadband;if(s.turnGain!==undefined)$('turnGain').value=s.turnGain;if(s.footOffset!==undefined)$('footOffset').value=s.footOffset;if(s.walkCenter!==undefined)$('walkCenter').value=s.walkCenter;if(s.walkBias!==undefined)$('walkBias').value=s.walkBias;if(s.waveLeg!==undefined)$('waveLeg').value=s.waveLeg;}if(scope===true || scope==='all' || scope==='gait')s.legs.forEach((v,i)=>legFields.forEach(([k])=>$(`leg${i}-${k}`).value=v[k]));if(scope===true || scope==="all" || scope==="cal")s.servos.forEach((v,i)=>{$(`servo${i}-angle`).value=v.angle;$(`servo${i}-slider`).value=v.angle;$(`servo${i}-dir`).value=v.dir;});}
function render(s){state=s;key=s.key;own=s.owner===client;$('connection').textContent=own?'已连接 · 本页控制':s.owner?'其他页面控制中':'已连接';$('connection').className='badge';$('motion').textContent=s.transitioning?'姿态过渡':(motionText[s.motion]||(s.walking?'行走中':'已停止'));$('summary').textContent=`标定${s.captured?'已读取':'未就绪'} · ${s.ready?'行走配置完整':'请检查站姿、方向和attach'} · 命令角无反馈`;$('speedActual').textContent=`${s.speed} 倍 / ${(4/s.speed).toFixed(3)} 秒`;$('turnGainActual').textContent=`当前增益 ${s.turnGain===undefined?0.5:s.turnGain}`;$('footOffsetActual').textContent=`当前偏移 ${s.footOffset===undefined?0:s.footOffset} mm`;$('walkCenterActual').textContent=`当前步态中心 ${s.walkCenter===undefined?0:s.walkCenter} mm`;$('walkBiasActual').textContent=`当前直行偏置 ${s.walkBias===undefined?0:s.walkBias}`;$('calState').textContent=s.servos.map(v=>`${v.id}: ${v.stand}° / dir ${v.dir}`).join('，');$('network').textContent=`热点：${s.ap} · ${s.apIP}；路由器：${s.connected?s.ip:'尚未连接'}`;s.servos.forEach((v,i)=>{$(`servo${i}-actual`).textContent=`GPIO${v.pin} · ${v.attached?'已attach':'未attach'} · 命令${v.angle}° · 站姿${v.stand}° · dir ${v.dir}`;});s.legs.forEach((v,i)=>{$(`leg${i}-actual`).textContent=`当前：抬${v.lift} / 深${v.depth} / 步${v.stride} mm；时间${v.liftPercent}% / ${v.lowerPercent}%`;});document.querySelectorAll('[data-leg],#gaitSave,#gaitLoad,#gaitReset,[data-dir],#capture,#saveCal,#loadCal').forEach(el=>el.disabled=s.walking||s.transitioning);['forward','back','left','right','straight'].forEach(id=>$(id).disabled=!s.ready||s.transitioning);$('applyTurn').disabled=s.walking||s.transitioning;$('applyOffset').disabled=s.walking||s.transitioning;$('applyCenter').disabled=s.walking||s.transitioning||s.waving;$('applyBias').disabled=s.walking||s.transitioning||s.waving;$('applyWaveLeg').disabled=s.walking||s.transitioning||s.waving;$('wave').disabled=!s.ready||s.walking||s.transitioning||s.waving;
  // Wave leg is a 1-based ID in the state; keep the select in sync after a wave.
  if(s.waveLeg!==undefined)$('waveLeg').value=s.waveLeg;if(!initialized){syncInputs(s);initialized=true;}if(s.message&&s.message.includes('heartbeat lost'))note('手机心跳中断，机器人已停止并保持最后姿态。请重新明确开始前行。',true);}
async function refresh(sync=false,background=false){
  const {response,data:s}=await request('/api/state',{cache:'no-store'},2500,background);
  if(!response.ok)throw Error('状态读取失败');
  showState(s,sync);
}
function showState(s,sync=false){
  render(s);
  $('deadbandActual').textContent=`当前死区 ${s.deadband}°`;
  if(sync)syncInputs(s,sync);
}
async function run(cmd,sync=false){
  if(cmd==='stop')return stop();
  if(busy||stopInProgress){note('上一条指令尚未完成，请稍候。',true);return;}
  busy=true;
  stopRequested=false;
  backgroundRequest?.abort();
  try{
    const result=await post('/api/command',{cmd});
    if(!stopRequested){
      if(!['s','list','ws','h','help'].includes(cmd))own=true;
      note(result.message);
      // Routine commands leave the next status read to the background poll.
      if(sync){
        try{await refresh(sync);}
        catch(e){if(!stopRequested)note('指令已确认，状态未刷新：'+e.message,true);}
      }
    }
  }catch(e){
    if(!stopRequested)note('指令未获确认：'+e.message,true);
  }finally{
    busy=false;
    if(stopRequested){
      // A pending command can arrive after the urgent stop. Reassert it.
      if(stopInProgress)await stopInProgress;
      await stop();
    }else tick();
  }
}
function stop(){
  stopRequested=true;
  own=false;
  backgroundRequest?.abort();
  if(stopInProgress)return stopInProgress;
  stopInProgress=(async()=>{
    try{const result=await post('/api/command',{cmd:'stop'});note(result.message);}
    catch(e){note('停止未获确认：'+e.message+'。已停止发送心跳。',true);}
    finally{stopInProgress=null;}
  })();
  return stopInProgress;
}
function guard(fn){return async e=>{if(e)e.preventDefault();try{await fn();}catch(err){note(err.message,true);}};}
$('applySpeed').onclick=guard(()=>run('walk speed '+value('speed')));$('stand').onclick=()=>run('stand');$('forward').onclick=()=>run('walk');$('back').onclick=()=>run('walk back');$('left').onclick=()=>run('walk left');$('right').onclick=()=>run('walk right');$('straight').onclick=()=>run('walk straight');$('stop').onclick=stop;$('refresh').onclick=guard(()=>refresh(true));$('applyTurn').onclick=guard(()=>run('walk turn '+value('turnGain')));$('applyOffset').onclick=guard(()=>run('foot offset '+value('footOffset')));$('applyCenter').onclick=guard(()=>run('walk center '+value('walkCenter')));$('applyBias').onclick=guard(()=>run('walk bias '+value('walkBias')));$('wave').onclick=()=>run('wave');$('applyWaveLeg').onclick=guard(()=>run('wave leg '+value('waveLeg')));
$('applyDeadband').onclick=guard(()=>run('walk deadband '+value('deadband')));
document.querySelectorAll('[data-leg]').forEach(b=>b.onclick=guard(()=>{const i=Number(b.dataset.leg),v=legFields.map(([k])=>value(`leg${i}-${k}`));if(v[3]+v[4]>80)throw Error('抬脚与放脚时间之和不能超过80%');return run(`walk set ${i+1} ${v.join(' ')}`);}));
document.querySelectorAll('[data-servo]').forEach(b=>b.onclick=guard(()=>{const i=Number(b.dataset.servo);return run(`set ${i+1} ${value(`servo${i}-angle`)}`);}));
document.querySelectorAll('[data-dir]').forEach(b=>b.onclick=guard(()=>{const i=Number(b.dataset.dir),d=value(`servo${i}-dir`);if(d!==1&&d!==-1)throw Error('请选择 +1 或 -1');return run(`stand direction ${i+1} ${d}`);}));
$('allSet').onclick=guard(()=>{const v=value('allAngle');if(confirm(`确定将全部8路命令到${v}°？这不是自动站姿。`))return run('all '+v);});$('init').onclick=()=>{if(confirm('确定全部命令到90°？90°不是实际站姿。'))run('init');};
$('capture').onclick=()=>{if(confirm('确认已摆好65mm参考站姿，并记录当前八路命令角？'))run('stand record','cal');};
$('saveCal').onclick=()=>{if(confirm('将当前站姿与方向保存到ESP32闪存？'))run('stand save');};
$('loadCal').onclick=()=>run('stand load','cal');
$('gaitSave').onclick=()=>run('walk save');
$('gaitLoad').onclick=()=>run('walk load','gait');
$('gaitReset').onclick=()=>{if(confirm('将当前步态参数恢复为默认值？确认后可另行保存。'))run('walk reset','gait');};
$('commandForm').onsubmit=guard(()=>{const cmd=$('command').value.trim();if(['stand record','stand save','walk save','init'].includes(cmd)&&!confirm('确认执行 '+cmd+'？'))return;return run(cmd,true);});
$('wifiForm').onsubmit=guard(async()=>{const j=await post('/api/wifi',{ssid:$('ssid').value,password:$('password').value});$('password').value='';note(j.message);});
async function tick(){
  if(ticking||busy||stopInProgress||document.hidden)return;
  ticking=true;
  try{
    if(own&&!stopRequested){
      try{
        const status=await post('/api/heartbeat',{},true);
        if(!busy&&!stopInProgress)showState(status);
        return;
      }catch(e){
        if(e.name==='AbortError')return;
        own=false;
      }
    }
    if(!busy&&!stopInProgress)await refresh(false,true);
  }catch(e){
    if(e.name!=='AbortError'){
      $('connection').textContent='连接异常';
      $('connection').className='badge off';
    }
  }finally{ticking=false;}
}
document.addEventListener('visibilitychange',()=>{if(document.hidden&&own)stop();else if(!document.hidden)tick();});
window.addEventListener('pagehide',()=>{own=false;});
tick();setInterval(tick,700);
</script></body></html>)ROBOTPAGE";
