/** Small adapter to the unmodified Nightshift execution and verifier APIs. */
export const PLANNING_RUBRIC = `# Synthetic Graduation Loop practice
## Must
- Gives exactly one small, concrete speaking action that can be tried in a class tomorrow.
- Includes one brief question for reflecting on that action after the attempt.
- Defines graduation as an observable speaking action initiated without a reminder on at least two occasions, rather than a feeling or continued app engagement.
- Uses supportive language and makes no diagnosis, clinical promise, or request for personal data.
`;

export function assessRun(record) {
  const verify = record.events?.filter(e => e.t === 'verify').at(-1);
  const answer = record.attempts?.find(a => a?.seq === record.job?.winner_seq)?.text || '';
  const quality = record.job?.quality;
  const accuracySupported = verify?.verdict === 'supported' && !verify.timed_out && verify.scores?.length > 0;
  const qualitySupported = verify?.verdict === 'meets_bar' && verify.panel?.ran === true && !verify.panel?.timed_out
    && quality?.graded_weight === 1 && quality?.scorecard?.length > 0 && quality.scorecard.every(c => c.score != null);
  const supported = accuracySupported || qualitySupported;
  let independent=verify?.judge_was_racer === false;
  let independenceBasis='native verification event';
  if(verify?.judge_mode==='quality' && verify.judge_was_racer==null) {
    let reviewer=null;
    const generators=[];
    for(const lane of record.lanes || []) if(lane.id==='verifier' && lane.races===false) reviewer=lane.model;
    for(const attempt of record.attempts || []) {
      const model=typeof attempt.model==='string'?attempt.model:(attempt.model?.resolved || attempt.model?.requested);
      if(model) generators.push(model);
    }
    independent=!!reviewer && generators.length>0 && !generators.includes(reviewer);
    independenceBasis='native fleet verifier lane compared with recorded generator identities; quality event has no identity fields';
  }
  return {hasAnswer:!!answer.trim(), hasReceipt:!!record.receipt?.receipt_id,
    winningText:answer,
    verifierVerdict:verify?.verdict ?? null, verifierReason:verify?.panel?.reason ?? null,
    verifierIndependent:independent, verifierIndependenceBasis:independenceBasis,
    usableVerifiedAnswer:!!answer.trim() && !!record.receipt?.receipt_id && !!supported};
}

export async function connectLocal(rt, models = ['llama3.2:3b','qwen2.5:7b'], judgeModel = null) {
  const input = {presetId:'ollama',url:'http://127.0.0.1:11435/v1',concurrency:1};
  const test = await rt.localNet.testConnection(input,{modelId:models[0]});
  if (!test.ok) throw new Error(test.error?.message || 'Local model connection failed. Check the Ollama terminal.');
  const selected=[];
  for (const row of test.models) if (models.includes(row.id)) selected.push(row);
  if (selected.length !== models.length) throw new Error('Download the selected local models first.');
  let existing=null;
  for (const previous of rt.localNet.list()) if (previous.base === input.url) existing=previous;
  const saved = rt.localNet.save({...input,...(existing ? {id:existing.id} : {}),lastTest:test,models:selected});
  const generator=rt.localNet.rowId(saved.id,models[0]);
  const grader=judgeModel || rt.localNet.rowId(saved.id,models[1]);
  await rt.fleets.save({id:'lab-local-pair',name:'Local generator and independent judge',
    lanes:[{id:'lab-generator',model:generator,role:'race'},{id:'verifier',model:grader,role:'verify',races:false}]});
  const fleet = await rt.fleets.activate('lab-local-pair',{fill:'named'});
  if (!fleet.ok) throw new Error('Local fleet could not start: ' + JSON.stringify(fleet));
  return {test,saved,fleet,generator,grader,lanes:rt.liveLanes()};
}

export async function connectDeepSeek(rt, generatorModel, judgeModel) {
  if (!generatorModel || !judgeModel || generatorModel === judgeModel) {
    throw new Error('DeepSeek generation and verification require two different models.');
  }
  const generator = `meterless-proxy/${generatorModel}`;
  const grader = `meterless-proxy/${judgeModel}`;
  const judgeRow = rt.findModel?.(grader);
  if (!judgeRow) throw new Error('The configured DeepSeek verifier is missing from Nightshift’s model catalog.');
  let generatorRow = rt.findModel?.(generator);
  if (!generatorRow) {
    if (!Array.isArray(rt.MODELS)) throw new Error('Nightshift’s model catalog is unavailable.');
    generatorRow = {...judgeRow,id:generator,provider:'meterless-proxy',name:'DeepSeek V4 Pro (official API)',
      family:'deepseek',kind:'cloud',ctx:32768,maxOut:1200,costInM:1.32,costOutM:3.96};
    rt.MODELS.push(generatorRow);
  }
  // The web engine reports a provider response's native model suffix
  // (`deepseek-v4-pro`) in resolved_model. Alias that suffix back to the
  // provider-qualified catalog row so Nightshift can confirm the pin.
  if (!rt.findModel?.(generatorModel)) {
    if (!Array.isArray(rt.MODELS)) throw new Error('Nightshift’s model catalog is unavailable.');
    rt.MODELS.push({...generatorRow,id:generatorModel,aliasOf:generator});
  }
  // The Flash lane also goes to the official DeepSeek API, so keep its
  // receipt estimates aligned with the API's conservative peak rates.
  Object.assign(judgeRow,{provider:'meterless-proxy',family:'deepseek',kind:'cloud',ctx:32768,
    costInM:0.3,costOutM:1.2});
  const saved = await rt.fleets.save({id:'lab-deepseek-pair',name:'DeepSeek generator and independent verifier',
    lanes:[{id:'lab-generator',model:generator,role:'race'},{id:'verifier',model:grader,role:'verify',races:false}]});
  const fleet = await rt.fleets.activate('lab-deepseek-pair',{fill:'named'});
  if (!fleet.ok) throw new Error('DeepSeek fleet could not start: ' + JSON.stringify(fleet));
  return {saved,fleet,generator,grader,lanes:rt.liveLanes()};
}

export function snapshotJob(rt,id) {
  const job=rt.jobs.get(id);
  const attempts=[];
  for (let seq=1;seq<=(job.generated||0);seq++) {
    const attempt=rt.jobs.attempt(id,seq);
    if (attempt) attempts.push(attempt);
  }
  const record={job,events:rt.jobs.readEvents(id),attempts,receipt:rt.jobs.receipt(id),outcome:rt.jobs.outcome(id),lanes:rt.liveLanes()};
  record.assessment=assessRun(record);
  return record;
}

export async function runProof(rt, prompt, update = () => {}, options = {}) {
  let connection, direct = null;
  if (options.deepseek) {
    update('Connecting DeepSeek generation and independent verification...');
    connection=await connectDeepSeek(rt,options.generatorModel,options.judgeModel);
  } else {
    update('Testing the local model connection...');
    connection=await connectLocal(rt,options.models,options.judgeModel);
    direct = await rt.callProvider({model:connection.generator,messages:[{role:'user',content:'Reply with LOCAL TEST OK.'}],max_tokens:40,temperature:0});
  }
  update('Running one Nightshift candidate and its independent grader...');
  const submitted = rt.jobs.submit({kind:'best_of_n',n:1,messages:[{role:'user',content:prompt}],
    window:'now',privacy:options.privacy || 'edge-only',judge_mode:'quality',judge_options:{rubric_text:options.rubric || PLANNING_RUBRIC,rubric_source:'authored'},selector:'verifier_panel',
    app:options.app || 'nightshift-local-lab',diversity:{level:'off'},attempt_budget:{level:'low'}});
  if (!submitted.id) throw new Error('Nightshift did not return a job ID.');
  if (options.onSubmitted) options.onSubmitted(submitted.id);
  const until = Date.now()+600000;
  while (!['completed','errored','cancelled'].includes(rt.jobs.get(submitted.id)?.status)) {
    if (Date.now()>until) throw new Error('Still running after ten minutes. Inspect the job in Nightshift before retrying.');
    const job=rt.jobs.get(submitted.id);
    update(`Nightshift ${job.status}: ${job.generated || 0} attempts recorded. Waiting for generation and grading...`);
    await new Promise(resolve => setTimeout(resolve,1000));
  }
  const record=snapshotJob(rt,submitted.id);
  if (direct) record.direct={text:direct.text,model:direct.model,usage:direct.usage};
  return record;
}

if (typeof document !== 'undefined' && document.getElementById('nightshift')) {
  const ui={frame:document.getElementById('nightshift'),run:document.getElementById('run'),save:document.getElementById('save'),
    status:document.getElementById('status'),answer:document.getElementById('answer'),verification:document.getElementById('verification'),
    receipt:document.getElementById('receipt'),prompt:document.getElementById('prompt')};
  function showStatus(text) {ui.status.replaceChildren(document.createTextNode(text));}
  let last=null;
  const ready=setInterval(()=>{
    if (!ui.frame.contentWindow.RT?.localNet) return;
    clearInterval(ready);ui.run.disabled=false;
    showStatus('Ready. Press the button to test the connection and run a real job.');
  },250);
  ui.run.onclick=async()=>{
    ui.run.disabled=true;ui.save.disabled=true;last=null;
    ui.answer.textContent='Waiting for this run...';ui.verification.textContent='Waiting for this run...';ui.receipt.textContent='Waiting for this run...';
    try {
      last=await runProof(ui.frame.contentWindow.RT,ui.prompt.value,showStatus);
      let answer='No winning answer was returned.';
      for (const attempt of last.attempts) if (attempt.seq === last.job.winner_seq) answer=attempt.text;
      ui.answer.textContent=answer;
      ui.verification.textContent=JSON.stringify({assessment:last.assessment,quality:last.job.quality,outcome:last.outcome},null,2);
      ui.receipt.textContent=JSON.stringify(last.receipt,null,2);
      showStatus(last.assessment.usableVerifiedAnswer ? 'Answer + passing rubric verdict + actual browser receipt returned.' : 'Job ended without a fully supported answer. Inspect the actual verification below.');
      ui.save.disabled=false;
      ui.frame.contentWindow.NSNav?.open(last.job.id);
    } catch(e) {showStatus(e.message);}
    finally {ui.run.disabled=false;}
  };
  ui.save.onclick=()=>{
    if (!last) return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(last,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`nightshift-${last.job.id}.json`;a.click();URL.revokeObjectURL(url);
  };
}
