"""Standalone, escaped HTML and Markdown; no remote assets or script execution."""

from html import escape
import re

COPY = {
    "en": {
        "title": "Your code changed. Here's the handoff.", "eyebrow": "KNOWLEDGE DEBT / CODE HANDOFF",
        "intro": "Understand the behaviors worth checking before you maintain this change.",
        "files": "changed Python files", "behaviors": "supported behaviors", "review": "changed since last guide",
        "scope": "Responsibility scope", "base": "Baseline", "target": "Target", "snapshot": "Source snapshot",
        "facts": "Source facts", "context": "Why this deserves attention", "unknown": "What is not established",
        "question": "Check your understanding", "source": "Inspect captured source", "before": "Baseline facts",
        "prior": "Facts in your previous guide", "map": "Local evidence map", "map_note": "Source facts grouped for reading, not a runtime execution trace.",
        "general": "General maintenance guidance · not inferred author intent",
        "read_only": "Reading this guide records no understanding evidence. Answer and self-check with kdebt drill.",
        "boundary": "A guide with boundaries", "offline": "Generated locally from Git and Python AST. No model was called. No code was executed.",
        "limits": "Only semaphore construction, counted retry patterns and finally cleanup are supported. Dynamic calls and cross-file dependencies remain unresolved.",
        "empty": "No supported behavior found in this scope. This is not proof that the change is safe or understood.",
        "changed": "Changed files", "unsupported": "No supported cards", "warnings": "Analysis gaps",
        "removed": "Removed relative to baseline", "removed_prior": "Removed since the previous guide",
        "none": "None", "navigation": "In this guide", "facts_only": "FACTS EDITION", "status": "Recorded self-check",
        "stale": "This card could not be revalidated. The source below is from an older guide.",
        "footer": "Built to help you take responsibility for code. Evidence is not a mastery score.",
    },
    "zh": {
        "title": "代码写完了，接下来由你接手。", "eyebrow": "KNOWLEDGE DEBT / 代码接手指南",
        "intro": "先看懂这次改动中值得关注的行为，再决定如何维护。",
        "files": "个 Python 文件有变化", "behaviors": "个已支持的行为", "review": "项说明在上次生成后变化",
        "scope": "责任范围", "base": "比较基线", "target": "目标版本", "snapshot": "源码快照",
        "facts": "源码直接支持的事实", "context": "为什么值得关注", "unknown": "目前还不能确定",
        "question": "检查一下自己的理解", "source": "查看已捕获的源码", "before": "基线版本的事实",
        "prior": "上次指南中的事实", "map": "局部事实关系", "map_note": "按信息类型组织的源码事实，不代表运行时执行流程。",
        "general": "一般性维护建议 · 不代表已确认的设计动机",
        "read_only": "阅读指南不会记录为已理解。需要记录回答时，请运行 kdebt drill 并自行核对事实。",
        "boundary": "说明的边界同样重要", "offline": "基于 Git 与 Python AST 在本地生成，未调用模型，也未执行仓库代码。",
        "limits": "当前仅支持 semaphore 构造、计数重试形态和 finally 清理。动态调用与跨文件依赖仍需人工确认。",
        "empty": "当前范围没有识别到已支持的行为。这不代表改动安全，也不代表已经理解。",
        "changed": "发生变化的文件", "unsupported": "没有已支持的说明卡片", "warnings": "分析缺口",
        "removed": "相对基线已移除", "removed_prior": "相对上次指南已移除",
        "none": "无", "navigation": "阅读导航", "facts_only": "离线事实版", "status": "已有自查记录",
        "stale": "这张卡片暂时无法重新验证，下面保留的是旧指南中的源码。",
        "footer": "帮助你接手代码，而不是为理解程度制造一个分数。",
    },
}

BEHAVIORS = {
    "en": {
        "concurrency": ("Where the concurrency limit lives", "A semaphore only coordinates work that shares and uses that object. Construction scope and matching uses are worth inspecting before changing a limit.", ["Construction", "Initial value", "Scope", "Direct-body uses"]),
        "retry": ("What happens when an operation is retried", "A timeout does not by itself establish whether a remote write took effect. Check repeatability and exit conditions before broadening a retry policy.", ["Loop", "Handled failures", "Delay", "Exit"]),
        "cleanup": ("How cleanup is arranged", "A cleanup call inside finally is useful evidence, but earlier failures or conditions can still prevent it from completing. Inspect the surrounding exit paths.", ["Finally suite", "Cleanup calls"]),
    },
    "zh": {
        "concurrency": ("并发限制在何处创建和使用", "只有共享并使用同一限制器的任务，才可能受它共同约束。修改并发上限前，需要确认构造位置、对象生命周期与使用范围。", ["构造位置", "初始参数", "所在作用域", "当前函数体中的使用"]),
        "retry": ("失败之后，操作会如何重试", "超时本身不能证明远端写入没有发生。扩大重试范围前，应确认操作能否安全重复，以及成功或失败后如何退出。", ["计数循环", "异常处理", "等待条件", "退出语句"]),
        "cleanup": ("资源清理是怎样安排的", "finally 中存在清理调用，不等于每条路径都能完成清理。需要进一步检查条件分支、前序异常与资源归属。", ["finally 结构", "清理调用"]),
    },
}

LABELS = {
    "en": {"added": "Added vs base", "changed": "Changed vs base", "unchanged": "Unchanged", "removed": "Removed", "unknown": "Unknown", "first": "First guide", "new": "New since guide", "needs_review": "Recheck explanation", "unverified": "Cannot revalidate", "restored": "Revalidated", "unrecorded": "No answer recorded", "answer_recorded": "Answer only", "partial": "Partial self-check", "self_checked": "Full fact self-check", "stale": "Answer needs recheck"},
    "zh": {"added": "相对基线新增", "changed": "相对基线变化", "unchanged": "未变化", "removed": "已移除", "unknown": "未知", "first": "首次生成", "new": "上次之后新增", "needs_review": "说明需要复核", "unverified": "无法验证", "restored": "恢复验证", "unrecorded": "尚未记录回答", "answer_recorded": "仅记录回答", "partial": "部分事实自查", "self_checked": "全部事实自查", "stale": "回答需要复核"},
}

CSS = """
:root{color-scheme:light;--ink:#172a32;--muted:#526773;--line:#dce5e4;--teal:#12685d;--orange:#a34615}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f6f3;color:var(--ink);font:15px/1.7 system-ui,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif}a{color:var(--teal);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid #d27736;outline-offset:4px}
.top{background:var(--ink);color:#fff;padding:18px max(24px,calc((100vw - 1200px)/2));display:flex;justify-content:space-between;gap:20px;font-size:12px;letter-spacing:.12em}.top span:last-child{color:#b4dfcd}
.wrap{max-width:1248px;margin:auto;padding:48px 24px}.eyebrow{color:var(--teal);font-size:12px;font-weight:750;letter-spacing:.15em}.hero h1{font-size:clamp(28px,3.4vw,46px);line-height:1.25;letter-spacing:-.035em;margin:12px 0 16px}.hero p{color:var(--muted);font-size:17px;max-width:800px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:30px 0}.metric{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px 24px}.metric b{display:block;font-size:32px;line-height:1.25}.metric span{color:var(--muted);font-size:13px}.compare{padding:14px 18px;background:#e6efea;border-radius:8px;display:flex;flex-wrap:wrap;gap:12px 28px;font-size:13px}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:28px;margin-top:32px}.main{min-width:0}.sidebar{min-width:0}.aside-inner{position:sticky;top:24px}.sidebar h2{font-size:14px}.sidebar p,.sidebar li{color:var(--muted);font-size:13px}.sidebar ul{padding-left:18px}.sidebar a{display:block;margin:10px 0}.card{background:white;border:1px solid var(--line);border-radius:14px;margin-bottom:24px;overflow:hidden;scroll-margin-top:20px}.card-head{padding:24px 26px 18px;border-bottom:1px solid var(--line)}.card h2{font-size:23px;line-height:1.4;margin:10px 0}.location{font:12px/1.6 ui-monospace,monospace;color:var(--muted);overflow-wrap:anywhere}.badges{display:flex;gap:8px;flex-wrap:wrap}.badge{border-radius:5px;font-size:11px;font-weight:700;padding:3px 8px;color:var(--teal);background:#e9f4ee}.badge.warn{background:#fff0dd;color:var(--orange)}.body{padding:24px 26px}.body h3{font-size:14px;margin:22px 0 8px}.body h3:first-child{margin-top:0}.caption{font-size:12px;color:var(--muted);margin:6px 0 12px}.context{border-left:3px solid #94bdae;padding-left:14px}.unknown{background:#fff6e9;border:1px solid #efdfc6;padding:14px 16px;border-radius:8px;font-size:14px}.map{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0 20px}.node{background:#f2f7f4;border:1px solid #dbe8df;border-radius:8px;padding:12px;min-width:0}.node b{display:block;font-size:11px;color:var(--teal);margin-bottom:4px}.node span{font-size:12px;overflow-wrap:anywhere;display:block}.facts{padding-left:22px}.facts li{padding-left:2px;margin-bottom:12px;overflow-wrap:anywhere}.facts a{font-size:12px;white-space:nowrap}details{border-top:1px solid var(--line);padding:14px 0}summary{cursor:pointer;font-size:14px;font-weight:650}.source{background:#172a32;color:#dcece8;border-radius:8px;overflow:auto;padding:12px;font:12px/1.75 ui-monospace,monospace;max-height:420px}.source .line{display:block;white-space:pre}.number{color:#88a6ab;display:inline-block;min-width:40px;user-select:none}.source .line:target{background:#35584f}.fact-code{white-space:pre-wrap;overflow-wrap:anywhere}.question{background:#f1f6fb;border-radius:8px;padding:16px}.file-list{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px 24px;margin-bottom:24px}.file-list h2{font-size:18px;margin-top:0}.file{display:flex;gap:12px;justify-content:space-between;border-top:1px solid var(--line);padding:10px 0;font-size:13px;overflow-wrap:anywhere}.file span{flex-shrink:0;color:var(--muted)}.empty{padding:24px;background:white;border:1px dashed #b5c6bd;border-radius:12px}.footer{border-top:1px solid var(--line);margin-top:30px;padding-top:20px;font-size:12px;color:var(--muted);overflow-wrap:anywhere}
@media(max-width:850px){.layout{grid-template-columns:1fr}.sidebar{grid-row:1}.aside-inner{position:static}.sidebar nav{display:none}.wrap{padding:28px 16px}.metrics{gap:8px}.metric{padding:14px}.metric b{font-size:26px}.card-head,.body{padding:20px}.top{padding:16px;letter-spacing:.05em}.top span:last-child{display:none}}
@media(max-width:440px){.metrics{grid-template-columns:1fr}.metric{display:flex;align-items:center;gap:14px}.map{grid-template-columns:1fr}.file{display:block}.file span{display:block}}
@media print{body{background:white}.top,.sidebar{display:none}.wrap{padding:0}.layout{display:block}.card{break-inside:avoid}.source{max-height:none}.hero h1{font-size:28px}}
"""
CSS += "\n.hero h1{text-wrap:balance}@media(max-width:850px){.sidebar{grid-row:auto}}\n"


def e(value):
    return escape(str(value), quote=True)


def source_html(card, snippet, prefix):
    if not snippet:
        return ""
    lines = "".join(f'<span class="line" id="{prefix}-{card["id"]}-L{snippet["start"] + i}"><span class="number">{snippet["start"] + i}</span>{e(line)}</span>'
                    for i, line in enumerate(snippet["text"].splitlines()))
    return f'<pre class="source">{lines}</pre>'


def card_html(card, language):
    t, labels = COPY[language], LABELS[language]
    title, context, nodes = BEHAVIORS[language][card["kind"]]
    badges = "".join(f'<span class="badge {"warn" if state in ("needs_review", "unverified", "unknown") else ""}">{e(labels[state])}</span>'
                     for state in (card["change"], card["since_guide"]))
    facts = []
    for fact in card["facts"]:
        anchor = f'fact-{card["id"]}-{fact["id"]}'
        facts.append(f'<li>{e(fact["text"])} <a href="#{anchor}">L{fact["line"]}</a>'
                     f'<details id="{anchor}"><summary>{e(card["path"])}:{fact["line"]}</summary>'
                     f'<pre class="source fact-code">{e(fact["source"])}</pre></details></li>')
    diagram = "".join(f'<div class="node"><b>{e(nodes[min(i, len(nodes)-1)])}</b><span>{e(f["text"])}</span></div>'
                      for i, f in enumerate(card["facts"][:4]))
    old = ""
    for key, heading in (("before_facts", "before"), ("prior_facts", "prior")):
        if card.get(key):
            old += f'<details><summary>{e(t[heading])}</summary><ul class="facts">' + "".join(
                f'<li>{e(f["text"])} <span class="location">L{f["line"]}</span></li>' for f in card[key]) + '</ul>'
            old += source_html(card, card.get("before_snippet" if key == "before_facts" else "prior_snippet"), heading) + '</details>'
    stale = f'<p class="unknown">{e(t["stale"])}</p>' if not card["verified"] else ""
    return f'''<article class="card" id="card-{card['id']}"><header class="card-head"><div class="badges">{badges}</div>
<h2>{e(title)}</h2><div class="location">{e(card['path'])}:{card['line']} · {e(card['symbol'])}</div></header>
<div class="body">{stale}<h3>{e(t['context'])}</h3><p class="caption">{e(t['general'])}</p><p class="context">{e(context)}</p>
<h3>{e(t['map'])}</h3><p class="caption">{e(t['map_note'])}</p><div class="map">{diagram}</div>
<h3>{e(t['facts'])}</h3><ol class="facts">{''.join(facts)}</ol>
<h3>{e(t['unknown'])}</h3><p class="unknown">{e(card['caveat'])}</p>
{old}<details><summary>{e(t['source'])}</summary>{source_html(card, card['snippet'], 'current')}</details>
<details><summary>{e(t['question'])}</summary><div class="question">{e(card['question'])}</div>
<p class="caption">{e(t['read_only'])}</p><p class="caption">{e(t['status'])}: {e(labels[card['evidence_state']])}</p></details></div></article>'''


def render_html(report):
    lang = report["language"]
    t, labels = COPY[lang], LABELS[lang]
    summary = report["summary"]
    metrics = "".join(f'<div class="metric"><b>{summary[key]}</b><span>{e(t[label])}</span></div>'
                      for key, label in (("changed_files", "files"), ("current_behaviors", "behaviors"), ("needs_review", "review")))
    cards = "".join(card_html(c, lang) for c in report["cards"]) or f'<div class="empty">{e(t["empty"])}</div>'
    files = ''.join(f'<div class="file"><div>{e(f["path"])}{("<br>" + e(t["unsupported"])) if not f["supported_cards"] else ""}</div><span>{e(labels[f["change"]])}</span></div>' for f in report['files']) or e(t['none'])
    warnings = report["warnings"] + report["baseline_warnings"]
    gaps = (f'<section class="file-list"><h2>{e(t["warnings"])}</h2>' + ''.join(f'<p>{e(w["path"])}: {e(w["reason"])}</p>' for w in warnings) + '</section>') if warnings else ''
    removed = ''
    for key, label in (("removed", "removed"), ("removed_since_guide", "removed_prior")):
        if report[key]:
            removed += f'<section class="file-list"><h2>{e(t[label])}</h2>' + ''.join(f'<p class="location">{e(c["path"])} · {e(c["symbol"])}</p>' for c in report[key]) + '</section>'
    nav = ''.join(f'<a href="#card-{c["id"]}">{e(c["symbol"])}</a>' for c in report['cards'])
    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Knowledge Debt · {e(report['repository'])}</title><style>{CSS}</style></head><body>
<div class="top"><span>KNOWLEDGE DEBT</span><span>{e(t['facts_only'])}</span></div>
<div class="wrap"><header class="hero"><div class="eyebrow">{e(t['eyebrow'])}</div><h1>{e(t['title'])}</h1><p>{e(t['intro'])}</p>
<div class="metrics">{metrics}</div><div class="compare"><span>{e(t['base'])} · {e(report['baseline'][:10])}</span><span>{e(t['target'])} · {e(report['target'][:12])}</span><span>{e(t['scope'])} · {e(', '.join(report['scopes']))}</span></div></header>
<div class="layout"><main class="main">{gaps}<section class="file-list"><h2>{e(t['changed'])}</h2>{files}</section>{cards}{removed}</main>
<aside class="sidebar"><div class="aside-inner"><h2>{e(t['boundary'])}</h2><p>{e(t['offline'])}</p><p>{e(t['limits'])}</p><p>{e(t['read_only'])}</p><nav aria-label="{e(t['navigation'])}"><h2>{e(t['navigation'])}</h2>{nav}</nav></div></aside></div>
<footer class="footer">{e(t['footer'])}<br>{e(t['snapshot'])}: {e(report['snapshot'])}<br>{e(report['generated_at'])}</footer></div></body></html>'''


def md(value):
    # Escape Markdown metacharacters and HTML supplied by repository content.
    text = escape(str(value), quote=False)
    for char in ("\\", "`", "*", "_", "[", "]", "#", "|", "~"):
        text = text.replace(char, "\\" + char)
    return text


def render_markdown(report):
    t, labels = COPY[report['language']], LABELS[report['language']]
    out = [f"# Knowledge Debt — {md(report['repository'])}", t['intro'],
           f"{t['base']}: {report['baseline']}\n\n{t['target']}: {report['target']}\n\n{t['snapshot']}: {report['snapshot']}",
           t['offline'], t['limits'], f"## {t['changed']}"]
    out.extend(f"- {md(f['path'])}: {labels[f['change']]} ({f['supported_cards']} cards)" for f in report['files'])
    if not report['cards']:
        out.append(t['empty'])
    for card in report['cards']:
        title, context, _ = BEHAVIORS[report['language']][card['kind']]
        out.extend([f"## {title} — {md(card['symbol'])}", f"{md(card['path'])}:{card['line']}",
                    f"{labels[card['change']]} · {labels[card['since_guide']]}",
                    t['stale'] if not card['verified'] else '', f"### {t['context']}", t['general'], context,
                    f"### {t['facts']}"])
        for fact in card['facts']:
            out.append(f"- {md(fact['text'])} ({md(card['path'])}:{fact['line']})")
            runs = re.findall(r"`+", fact['source'])
            fence = "`" * max(3, max((len(run) + 1 for run in runs), default=3))
            out.append(f"{fence}python\n{fact['source']}\n{fence}")
        out.extend([f"### {t['unknown']}", md(card['caveat'])])
        for key, label in (("before_facts", "before"), ("prior_facts", "prior")):
            if card.get(key):
                out.append(f"### {t[label]}")
                out.extend(f"- {md(f['text'])} (L{f['line']})" for f in card[key])
        out.extend([f"### {t['question']}", md(card['question']), t['read_only'],
                    f"{t['status']}: {labels[card['evidence_state']]}"])
    for key, label in (("removed", "removed"), ("removed_since_guide", "removed_prior")):
        if report[key]:
            out.append(f"## {t[label]}")
            out.extend(f"- {md(c['path'])}: {md(c['symbol'])}" for c in report[key])
    if report['warnings'] or report['baseline_warnings']:
        out.append(f"## {t['warnings']}")
        out.extend(f"- {md(w['path'])}: {md(w['reason'])}" for w in report['warnings'] + report['baseline_warnings'])
    return "\n\n".join(part for part in out if part) + "\n"
