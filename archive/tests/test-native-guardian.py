#!/usr/bin/env python3
"""Real native discovery through production guardian, fixture HOME, no model turn."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('test-bootstrap.py'))
fmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(fmod)
b,w=fmod.b,fmod.w


def run(claude,codex):
    f=fmod.BootstrapTests();f.setUp()
    try:
        options=f.options();options.claude=str(claude);options.codex=str(codex)
        with contextlib.redirect_stdout(io.StringIO()):
            doc,_,_=b.planned(options)
            options.plan=str(f.state/'native-plan.json');b.save(Path(options.plan),doc,True)
            options.approve=w.digest(w.encoded(doc));b.apply(options)
        work=f.root/'work';work.mkdir()
        (f.home/'.codex/config.toml').write_text('model_provider="fixture"\nmodel="gpt-5.3-codex"\n[model_providers.fixture]\nname="fixture"\nbase_url="http://127.0.0.1:9/v1"\nwire_api="responses"\nrequires_openai_auth=false\n')
        env=dict(HOME=str(f.home),PATH='/usr/bin:/bin',LC_ALL='C',TMPDIR=str(f.root),
                 CLAUDE_CONFIG_DIR=str(f.home/'.claude'),CODEX_HOME=str(f.home/'.codex'),
                 DISABLE_AUTOUPDATER='1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                 ANTHROPIC_BASE_URL='http://127.0.0.1:9',GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_NOSYSTEM='1')
        # Missing sync dependencies exercises coherent-A fallback without network.
        result={}
        for product,binary in [('claude',claude),('codex',codex)]:
            shim=f.root/(product+'-launch');shim.write_text(fmod.launcher.render(f.state,product));shim.chmod(0o700)
            if product=='claude':
                argv=['-p','--input-format','stream-json','--output-format','stream-json','--verbose','--settings','{"disableAllHooks":true}']
                packet=b'{"type":"control_request","request_id":"fixture","request":{"subtype":"initialize"}}\n'
            else:
                argv=['debug','prompt-input','--disable','hooks','fixture'];packet=b''
            direct=subprocess.run([str(binary),*argv],input=packet,env=env,cwd=work,capture_output=True,timeout=30)
            wrapped=subprocess.run([str(shim),*argv],input=packet,env=env,cwd=work,capture_output=True,timeout=30)
            assert direct.returncode==0, 'DIRECT_NATIVE_DISCOVERY_FAILED'
            assert wrapped.returncode==0, 'WRAPPED_NATIVE_DISCOVERY_FAILED'
            for name in b.a.SKILLS:
                assert name.encode() in direct.stdout and name.encode() in wrapped.stdout, 'NATIVE_SKILL_DISCOVERY_REGRESSION'
            time.sleep(.2)
            leases=f.src/'.git/ai-agent-launch-readers'
            records=[b.load(p) for p in leases.iterdir()] if leases.exists() else []
            evidence=[dict(agent=r.get('agent'),state=r['state'],evidence=r.get('evidence'))
                      for r in records if r.get('agent')==product]
            assert len(evidence)==1 and evidence[0]['state']=='UNCERTAIN_FAMILY', 'NATIVE_LIFETIME_EVIDENCE_CHANGED'
            assert evidence[0]['evidence']['missing']==['descendant_identities','continuous_descendant_lineage','descendant_exit_observations']
            result[product]=dict(discovery='PASS',six_skills=True,reader_evidence=evidence)
        b.verify_receipt(b.receipt(f.state),f.src,f.home)
        return dict(native=result,managed_drift=False,model_requests='NOT_RUN',credentials='NOT_USED')
    finally:f.doCleanups()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--claude',type=Path,required=True);p.add_argument('--codex',type=Path,required=True)
    args=p.parse_args();print(json.dumps(run(args.claude,args.codex),sort_keys=True))
