"""Serve an integrity-checked local extension of the founder's original demo."""
from pathlib import Path
import json
import re


def ensure_demo(root, fetch, validate):
    spec = json.loads(Path(__file__).with_name("little_jahsi.lock.json").read_text())
    dest = root / ".runtime" / "graduation-loop-original.html"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(validate(fetch(spec["url"]), spec))
    validate(dest.read_bytes(), spec)
    return dest


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Pinned Graduation Loop patch anchor changed; refusing a simulated fallback")
    return text.replace(old, new, 1)


def wire_demo(source):
    """Replace the simulated journey handler; preserve the rest of her application."""
    source = replace_once(source, '$("missionBtn").addEventListener("click", function(){',
                          '$("missionBtn").addEventListener("click", async function(){')
    start = source.index('    EngineAdapter.submit(JOURNEYS[state.goalKey].label, state.length);')
    end_marker = '      var m=JOURNEYS[state.goalKey]; state.journey=m;'
    end = source.index(end_marker, start) + len(end_marker)
    source = source[:start] + '''    var btn=this; btn.disabled=true;
    var requestKey=state.goalKey, requestLength=state.length, requestGoal=state.goalText;
    $("missionCard").classList.remove("show");
    $("nextMissionBtn").disabled=true;
    state.journey=null;
    try {
      var plan=await window.LJNightshift.generate({goal:requestGoal || JOURNEYS[requestKey].label, length:requestLength});
      if(state.goalKey!==requestKey || state.length!==requestLength || $("goalText").value.trim()!==requestGoal)
        throw new Error("The goal changed while Nightshift worked. Begin again for the new goal.");
      var m=Object.assign({}, JOURNEYS[requestKey], plan); state.journey=m;
''' + source[end:]
    source = replace_once(source, '    }, 1100);', '''    } catch(error) {
      state.journey=null;
      $("missionCard").classList.remove("show");
      toast(error.message);
    } finally { btn.disabled=false; }
''')
    source = replace_once(source, '    EngineAdapter.verdict();\n', '') if '    EngineAdapter.verdict();\n' in source else source
    # Reset also invalidates an outstanding asynchronous result.
    source = replace_once(source, '$("resetBtn").addEventListener("click", function(){',
                          '$("resetBtn").addEventListener("click", function(){ window.LJNightshift?.reset();')
    source = re.sub(r'<link[^>]+href="https://fonts\.[^>]+>\s*', '', source)
    source = replace_once(source, 'logAdapter("Zetaris ▸ write "+table', 'logAdapter("Local memory mirror ▸ write "+table')
    source = replace_once(source, 'nothing sent anywhere in this demo.',
                          'private check-ins stay on this page; only the goal goes to local Nightshift.')
    return replace_once(source, '</head>', '<script type="module" src="/graduation_bridge.mjs"></script>\n</head>')
