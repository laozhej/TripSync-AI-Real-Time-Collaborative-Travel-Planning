"""Optional axe checks for local real-browser UI verification (no app dependency)."""
import json
import os
from pathlib import Path

def audit(page, name):
    script=os.environ.get('UI_AXE_PATH')
    if not script:
        return
    if not page.evaluate("typeof window.axe !== 'undefined'"):
        page.add_script_tag(path=script)
    result=page.evaluate("""async () => {
        await document.fonts.ready;
        const result=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});
        return {violations:result.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),passes:result.passes.length,incomplete:result.incomplete.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))};
    }""")
    path=Path('.local/ui-audit');path.mkdir(parents=True,exist_ok=True)
    (path/(name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    assert not result['violations'],f'{name}: accessibility violations in {path/(name+".json")}'
    print(f'Axe {name}: zero WCAG A/AA violations; {result["passes"]} rules passed; {len(result["incomplete"])} require review')
