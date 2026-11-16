#!/usr/bin/env python3
"""Validate source-linked AI analysis, then render a self-contained local brief."""
import argparse
from datetime import datetime
import html
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


def validate(scan, analysis):
    if analysis.get("run_id") != scan["run_id"]:
        raise ValueError("Analysis must belong to this exact scan")
    rows = {r["id"]: r for r in scan["videos"]}
    selected = set(scan["selected_ids"])
    seen = set()
    for item in analysis["items"]:
        ident = item["video_id"]
        if ident in seen or ident not in rows:
            raise ValueError("Duplicate or unknown video ID")
        seen.add(ident)
        row = rows[ident]
        if item["source_url"] != row["url"] or urlparse(row["url"]).scheme != "https":
            raise ValueError("Original source link mismatch")
        sample = item.get("historical_demo", False)
        if sample and ident in selected:
            raise ValueError("Daily selected item cannot be relabelled as historical")
        if not sample and ident not in selected:
            raise ValueError("Unselected video cannot appear as a daily pick")
        if sample and (type(row.get("views")) is not int or row["views"] <= scan["rules"]["minimum_views_exclusive"] or
                       type(row.get("duration_seconds")) is not int or not 0 < row["duration_seconds"] < scan["rules"]["duration_under_seconds"]):
            raise ValueError("Historical demo must still meet view and runtime rules")
        if item["review_status"] == "unavailable":
            if not item.get("reason", "").strip() or item.get("shots") or item.get("hook"):
                raise ValueError("Unavailable videos need a reason and no invented analysis")
            continue
        if item["review_status"] != "reviewed":
            raise ValueError("Unfinished review")
        for key in ("review_method", "hook", "mechanism_hypothesis", "limits"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError("Missing analysis field: " + key)
        if not item.get("evidence"):
            raise ValueError("No viewing evidence")
        for evidence in item["evidence"]:
            if not 0 <= evidence["at_seconds"] < row["duration_seconds"] or not evidence["observation"].strip():
                raise ValueError("Evidence outside original runtime or empty observation")
        adaptation = item["adaptation"]
        for key in ("merchant", "concept", "format", "cta"):
            if not adaptation.get(key, "").strip():
                raise ValueError("Missing adaptation field: " + key)
        if not adaptation.get("assets") or not adaptation.get("qc"):
            raise ValueError("Assets and delivery checks are required")
        end = 0
        if len(item["shots"]) < 2:
            raise ValueError("Remake requires at least two shots")
        for shot in item["shots"]:
            if shot["start"] != end or shot["end"] <= shot["start"]:
                raise ValueError("Remake timeline must be continuous")
            if not all(isinstance(shot.get(k), str) and shot[k].strip() for k in ("visual", "copy", "audio")):
                raise ValueError("Each shot needs camera action, copy and audio/edit direction")
            end = shot["end"]
        if end != adaptation["duration_seconds"] or not 0 < end < 60:
            raise ValueError("Remake duration mismatch or outside short-video range")
    if not selected.issubset(seen):
        raise ValueError("Some selected videos have no review outcome")
    return rows


def localtime(value, timezone):
    return datetime.fromisoformat(value).astimezone(ZoneInfo(timezone)).strftime("%m-%d %H:%M")


def shot_text(item):
    a = item["adaptation"]
    text = f"{a['concept']}\n适合：{a['merchant']}\n{a['duration_seconds']} 秒 · {a['format']}\n素材：" + "、".join(a["assets"]) + "\n\n"
    for s in item["shots"]:
        text += f"{s['start']}–{s['end']}s\n画面：{s['visual']}\n字幕：{s['copy']}\n声音/剪辑：{s['audio']}\n\n"
    return text + "CTA：" + a["cta"] + "\n交片检查：" + "；".join(a["qc"])


def render(scan_path, analysis_path, out):
    scan, analysis = json.loads(scan_path.read_text()), json.loads(analysis_path.read_text())
    rows = validate(scan, analysis)
    out.mkdir(parents=True, exist_ok=True)
    esc = lambda x: html.escape(str(x), quote=True)
    coverage = scan["coverage"]
    examples = [i for i in analysis["items"] if i.get("historical_demo")]
    daily = [i for i in analysis["items"] if not i.get("historical_demo")]
    ts = localtime(scan["completed_at"], scan["timezone"])
    rules = scan['rules']
    ruletext = f"发布 {rules.get('lookback_hours',24)} 小时内 · 原片 1–{rules['duration_under_seconds']-1} 秒 · 公开播放 >{rules['minimum_views_exclusive']:,}"
    status = "本轮没有符合条件的新视频" if not scan["selected_ids"] else f"本轮选出 {len(scan['selected_ids'])} 条待研究视频"
    if scan["status"] == "coverage_insufficient":
        status = "原片数据覆盖不足，不能判断有无新视频"
    md = ["# Stillmore 每日电商视频研究简报", "", f"观测：{ts}（{scan['timezone']}）", "", status,
          f"来源 {coverage['readable_sources']}/{coverage['total_sources']} 可读；观测 {coverage['videos_observed']} 个视频；符合筛选 {coverage['qualifying_videos']} 个。",
          "筛选：" + ruletext + "。高播放不等于高销量。", ""]
    cards, scripts = [], {}
    for index, item in enumerate(daily + examples, 1):
        row = rows[item["video_id"]]
        sample = item.get("historical_demo")
        label = "历史演示 · 不计入今日结果" if sample else "本轮入选"
        md += [f"## {index}. {row['brand']} — {row['title']}", "", label, row["url"],
               f"公开播放 {row['views']:,} · {row['duration_seconds']} 秒 · 发布 {localtime(row['published'], scan['timezone'])} · 观测 {localtime(row['observed_at'], scan['timezone'])}", ""]
        if item["review_status"] == "unavailable":
            md += ["未能核实画面：" + item["reason"], ""]
            cards.append(f'<article class="card"><span class="tag">{esc(label)}</span><h2>{esc(row["title"])}</h2><p>{esc(item["reason"])}</p><a href="{esc(row["url"])}" target="_blank" rel="noopener">打开原视频 ↗</a></article>')
            continue
        a = item["adaptation"]
        md += ["### 创意拆解", "", "开场钩子：" + item["hook"], "", "传播机制假设：" + item["mechanism_hypothesis"], "", "证据边界：" + item["limits"], "", "观看方式：" + item["review_method"], "", "原片画面依据："]
        md += [f"- {e['at_seconds']}s：{e['observation']}" for e in item["evidence"]]
        md += ["", "### 原创复刻脚本", "", shot_text(item), ""]
        scripts[item["video_id"]] = shot_text(item)
        shotrows = ''.join(f'<tr><td class="time">{esc(s["start"])}–{esc(s["end"])}s</td><td>{esc(s["visual"])}</td><td>{esc(s["copy"])}</td><td>{esc(s["audio"])}</td></tr>' for s in item["shots"])
        evidence = ''.join(f'<li><b>{esc(e["at_seconds"])}s</b> {esc(e["observation"])}</li>' for e in item["evidence"])
        cards.append(f'''<article class="card" id="{esc(item['video_id'])}">
          <div class="card-top"><span class="tag">{esc(label)}</span><span class="brand">{index:02d} / {esc(row['brand'])}</span></div>
          <h2>{esc(row['title'])}</h2>
          <div class="metrics"><b>{row['views']:,}<small>公开播放</small></b><b>{row['duration_seconds']}s<small>原片时长</small></b><b>{esc(localtime(row['published'],scan['timezone']))}<small>发布时间 · {esc(scan["timezone"])}</small></b></div>
          <p class="note">计数观测于 {esc(localtime(row['observed_at'],scan['timezone']))}；非销量、转化率或自然流量证明。</p>
          <a class="source" href="{esc(row['url'])}" target="_blank" rel="noopener">观看原视频 ↗</a>
          <div class="breakdown"><section><h3>01 / 开场钩子</h3><p>{esc(item['hook'])}</p></section><section><h3>02 / 为什么值得研究</h3><p>{esc(item['mechanism_hypothesis'])}</p></section></div>
          <details><summary>查看原片依据与分析边界</summary><p>{esc(item['review_method'])}</p><ul>{evidence}</ul><p>{esc(item['limits'])}</p></details>
          <section class="remake"><div class="script-head"><div><span class="eyebrow">MAKE IT YOUR OWN</span><h3>{esc(a['concept'])}</h3></div><button data-copy="{esc(item['video_id'])}">复制脚本</button></div>
          <p>适合 {esc(a['merchant'])} · {a['duration_seconds']} 秒 · {esc(a['format'])}</p><p><b>准备：</b>{esc('、'.join(a['assets']))}</p>
          <div class="table-scroll"><table><thead><tr><th>时间</th><th>画面 / 动作</th><th>字幕 / 文案</th><th>声音 / 剪辑</th></tr></thead><tbody>{shotrows}</tbody></table></div>
          <p><b>下一步：</b>{esc(a['cta'])}</p><p class="note"><b>交片检查：</b>{esc('；'.join(a['qc']))}</p></section></article>''')
    recent = sorted((r for r in rows.values() if r.get('age_hours') is not None and 0 <= r['age_hours'] <= rules.get('lookback_hours',24) and type(r.get('duration_seconds')) is int and 0 < r['duration_seconds'] < rules['duration_under_seconds'] and type(r.get('views')) is int),key=lambda r:r.get('views') or 0,reverse=True)[:5]
    recent_html = ''.join(f'<tr><td><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["brand"])} · {esc(r["title"])}</a></td><td>{r.get("views",0):,}</td><td>{r["duration_seconds"]}s</td><td>{"低于播放门槛" if not r["eligible"] else "符合条件"}</td></tr>' for r in recent)
    source_html = ''.join(f'<tr><td>{esc(s["source"])}</td><td>{"原片频道" if s["kind"]=="channel" else "发现线索"}</td><td>{s.get("items",0)}</td><td>{"可读" if s["ok"] else "失败"}</td></tr>' for s in scan['sources'])
    sample_note = '<div class="section-title"><span class="eyebrow">OUTPUT PREVIEW</span><h2>完整交付长什么样</h2><p>以下为真实视频的历史演示，不计入今日入选。</p></div>' if examples else ''
    if recent:
        md += ['## 近期观察：未放宽门槛',''] + [f'- [{r["brand"]}：{r["title"]}]({r["url"]}) — {r["views"]:,} 次，{r["duration_seconds"]} 秒。' for r in recent]
    if analysis.get('lead_review_summary'):
        md += ['', '## 媒体线索回查', '', analysis['lead_review_summary']]
    md += ['', '## 覆盖与限制', '', *['- '+x for x in scan['limitations']], '', '简报由本次采集与 AI 审阅生成；每日执行由宿主的定时任务配置决定。']
    html_doc = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stillmore · Daily Video Brief</title><style>
      :root{--ink:#172020;--soft:#626c69;--line:#dce2dc;--paper:#f5f5ef;--accent:#ce4e35}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:inherit;text-underline-offset:4px}header,main,footer{max-width:1120px;margin:auto;padding:0 32px}nav{display:flex;justify-content:space-between;align-items:center;padding:26px 0;border-bottom:1px solid var(--line)}.logo{font-weight:800;font-size:23px;letter-spacing:-1px}.logo span{color:var(--accent)}.badge,.tag{font-size:12px;border:1px solid var(--line);border-radius:30px;padding:5px 12px}.hero{padding:52px 0 28px}.eyebrow{font-size:11px;font-weight:700;letter-spacing:2px;color:var(--accent)}h1{font-size:clamp(32px,5vw,55px);line-height:1.18;letter-spacing:-2px;max-width:850px;margin:18px 0}h2{font-size:25px;line-height:1.4;letter-spacing:-.5px}h3{font-size:17px}.lede{color:var(--soft);max-width:750px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:28px 0}.stat{background:var(--paper);padding:18px 22px}.stat b{display:block;font-size:30px;line-height:1.2}.stat small{color:var(--soft)}.today{border:1px solid var(--line);padding:24px 28px;border-radius:14px;background:#fff}.today h2{margin:0 0 10px;font-size:23px}.section-title{padding:48px 0 12px}.section-title h2{margin:8px 0}.section-title p,.note{font-size:13px;color:var(--soft)}.card{padding:30px;margin:22px 0 32px;border:1px solid var(--line);border-radius:18px;background:#fff}.card-top{display:flex;justify-content:space-between;align-items:center;gap:15px}.brand{font-size:12px;color:var(--soft)}.tag{background:#fcf0dc;color:#84571e;border-color:#efddba}.metrics{display:flex;gap:40px;margin:24px 0 8px}.metrics b{font-size:24px;line-height:1.3}.metrics small{display:block;font-size:11px;font-weight:400;color:var(--soft);margin-top:5px}.source{display:inline-block;margin:12px 0;background:var(--ink);color:#fff;border-radius:7px;padding:9px 18px;text-decoration:none;font-size:14px}.breakdown{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin:12px 0}.breakdown h3{font-size:13px;color:var(--accent)}p{margin:10px 0}details{border-top:1px solid var(--line);padding:16px 0}summary{cursor:pointer;font-size:14px;font-weight:600}.remake{margin-top:15px;padding:24px;border-radius:12px;background:#f1f4ed}.script-head{display:flex;justify-content:space-between;gap:20px;align-items:center}.script-head h3{font-size:21px;margin:6px 0}.table-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px;margin:16px 0}th{font-size:11px;letter-spacing:.5px;color:var(--soft)}th,td{padding:13px 12px;border-bottom:1px solid var(--line);vertical-align:top}.time{white-space:nowrap;font-weight:700;color:var(--accent)}button{border:1px solid var(--ink);background:transparent;border-radius:7px;padding:10px 16px;cursor:pointer;white-space:nowrap;color:var(--ink)}button:hover{background:var(--ink);color:#fff}footer{padding-top:30px;padding-bottom:45px;color:var(--soft);font-size:12px}footer div{border-top:1px solid var(--line);padding-top:20px;display:flex;justify-content:space-between;gap:20px}.coverage{margin:30px 0}.download{font-size:13px}.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:10px 20px;border-radius:8px;display:none}dialog{max-width:700px;width:90%;border:0;border-radius:12px}textarea{width:100%;height:350px;padding:14px;line-height:1.6} @media(max-width:650px){.logo{white-space:nowrap}.logo span[style]{display:none}nav{gap:12px}.badge{white-space:nowrap}header,main,footer{padding-left:18px;padding-right:18px}.hero{padding-top:35px}h1{letter-spacing:-1px}.stats{grid-template-columns:repeat(2,1fr)}.card{padding:20px}.metrics{gap:20px;flex-wrap:wrap}.metrics b{font-size:21px}.breakdown{grid-template-columns:1fr;gap:2px}.remake{padding:16px;margin-left:-4px;margin-right:-4px}.script-head{align-items:flex-start;flex-direction:column}.card-top{align-items:flex-start;flex-direction:column}.brand{order:-1}th,td{min-width:130px}.time{min-width:60px}footer div{flex-direction:column}.badge{font-size:10px}}
      </style><body><header><nav><div class="logo">stillmore<span>✳</span> <span style="font-size:12px;color:#626c69;letter-spacing:1px;margin-left:12px">TREND SCOUT</span></div><span class="badge">DAILY VIDEO BRIEF</span></nav><section class="hero"><span class="eyebrow">YOUR DAILY CREATIVE RESEARCH</span><h1>找到值得研究的视频，<br>带走能执行的下一条脚本。</h1><p class="lede">让 AI 每日发现、核实、拆解。每个入选视频都附原始链接与原创复刻脚本，数据与判断分开呈现。</p>'''
    html_doc += f'<div class="stats"><div class="stat"><b>{coverage["readable_sources"]}/{coverage["total_sources"]}</b><small>来源读取成功</small></div><div class="stat"><b>{coverage["videos_observed"]}</b><small>原视频观测</small></div><div class="stat"><b>{coverage["qualifying_videos"]}</b><small>本轮符合门槛</small></div><div class="stat"><b>{len(examples)}</b><small>历史演示案例</small></div></div><a class="download" href="report.md" download>下载完整 Markdown 简报 ↓</a></section></header><main>'
    html_doc += f'<section class="today"><span class="eyebrow">SCAN / {esc(ts)} · {esc(scan["timezone"])}</span><h2>{esc(status)}</h2><p>本轮保持：{esc(ruletext)}。</p><p class="note">近期低播放视频进入观察列表；媒体报道须回到原视频核实后才可入选。历史案例（如有）单独标注。</p><details><summary>查看近期视频与筛选情况</summary><div class="table-scroll"><table><thead><tr><th>原视频</th><th>播放</th><th>时长</th><th>状态</th></tr></thead><tbody>{recent_html}</tbody></table></div></details></section>'
    if analysis.get('lead_review_summary'):
        html_doc += '<p class="note">' + esc(analysis['lead_review_summary']) + '</p>'
    html_doc += ''.join(cards[:len(daily)]) + sample_note + ''.join(cards[len(daily):])
    html_doc += f'<details class="coverage"><summary>来源覆盖与数据限制 · {coverage["total_sources"]} 个入口</summary><p>自动原片计数来自 YouTube；TikTok / Instagram 目前只有新闻发现线索。公开播放不能证明销量、留存或自然增长。部分频道的时长未能核实，这类视频不会入选。</p><div class="table-scroll"><table><thead><tr><th>来源</th><th>用途</th><th>条目</th><th>状态</th></tr></thead><tbody>{source_html}</tbody></table></div></details></main><footer><div><span>Stillmore · 先研究创意，再用自己的商品与素材制作。</span><a href="https://stillmore.studio/" target="_blank" rel="noopener">了解 Stillmore ↗</a></div></footer><div class="toast" role="status">脚本已复制</div><dialog id="copyDialog"><p>脚本已选中，按 ⌘C / Ctrl+C 复制</p><textarea id="copyText" readonly></textarea><button id="closeDialog">关闭</button></dialog>'
    html_doc += '<script type="application/json" id="scripts">' + json.dumps(scripts, ensure_ascii=False).replace('<','\\u003c') + '</script>'
    html_doc += '''<script>const scripts=JSON.parse(document.querySelector('#scripts').textContent);document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const t=scripts[b.dataset.copy];try{if(location.protocol==='file:'||!navigator.clipboard)throw Error('clipboard');await Promise.race([navigator.clipboard.writeText(t),new Promise((_,reject)=>setTimeout(()=>reject(Error('timeout')),1500))]);const n=document.querySelector('.toast');n.style.display='block';setTimeout(()=>n.style.display='none',1800)}catch(e){document.querySelector('#copyText').value=t;document.querySelector('#copyDialog').showModal();document.querySelector('#copyText').select()}}));document.querySelector('#closeDialog').onclick=()=>document.querySelector('#copyDialog').close();</script></body></html>'''
    (out / 'index.html').write_text(html_doc)
    (out / 'report.md').write_text('\n'.join(md)+'\n')
    (out / 'validation.json').write_text(json.dumps({'passed':True,'daily_review_outcomes':len(daily),'historical_examples':len(examples),'run_id':scan['run_id']},indent=2)+'\n')
    print(str((out / 'index.html').resolve()))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scan',type=Path,required=True)
    p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    render(a.scan,a.analysis,a.out)
