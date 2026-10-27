import test from 'node:test';
import assert from 'node:assert/strict';
import {goalPrompt,goalRubric,verifiedJourney} from '../graduation_bridge.mjs';
import {connectDeepSeek} from '../proof.js';

function approvedRecord() {
  return {job:{winner_seq:1,quality:{graded_weight:1,scorecard:[{score:1}]}},
    attempts:[{seq:1,text:JSON.stringify({title:'One question',step:'Ask one question tomorrow.',check_in:'Did you ask it?',graduation:'Ask without reminders on at least two occasions.'})}],
    events:[{t:'verify',verdict:'meets_bar',judge_was_racer:false,panel:{ran:true,timed_out:false}}],
    receipt:{receipt_id:'real-record-required'},outcome:{status:'accepted'}};
}

test('approved native answer supplies the journey text; model text is not executable HTML',()=>{
  const record=approvedRecord();record.attempts[0].text=record.attempts[0].text.replace('One question','<img src=x onerror=alert(1)>');
  const result=verifiedJourney(record);assert.equal(result.title,'<img src=x onerror=alert(1)>');assert.deepEqual(result.steps,['Ask one question tomorrow.']);
});

test('rejected, timed-out, missing-receipt and self-judged runs cannot become journeys',()=>{
  const rejected=approvedRecord();rejected.outcome.status='rejected';assert.throws(()=>verifiedJourney(rejected));
  const timeout=approvedRecord();timeout.events[0].panel.timed_out=true;assert.throws(()=>verifiedJourney(timeout));
  const receipt=approvedRecord();receipt.receipt=null;assert.throws(()=>verifiedJourney(receipt));
  const self=approvedRecord();self.events[0].judge_was_racer=true;assert.throws(()=>verifiedJourney(self));
});

test('unreadable, incomplete and overlong generated text is preserved but not applied',()=>{
  for(const text of ['not JSON','{}',JSON.stringify({title:'a',step:'word '.repeat(101),check_in:'?',graduation:'two'})]) {
    const record=approvedRecord();record.attempts[0].text=text;assert.throws(()=>verifiedJourney(record));
  }
});

test('prompt bounds the goal and carries no profile, check-in or caretaker fields',()=>{
  assert.throws(goalPrompt.bind(null,{goal:''}));assert.throws(goalPrompt.bind(null,{goal:'x'.repeat(801)}));
  const prompt=goalPrompt({goal:'ask one question',length:'1 week',name:'PRIVATE',reflection:'PRIVATE'});
  assert.ok(prompt.includes('ask one question'));assert.ok(!prompt.includes('PRIVATE'));
  assert.ok(goalRubric('ask one question').includes('"ask one question"'));
  assert.throws(goalRubric.bind(null,'x'.repeat(400)));
});

test('native quality identity is derived from the actual fleet when its event omits identity fields',()=>{
  const record=approvedRecord();delete record.events[0].judge_was_racer;record.events[0].judge_mode='quality';
  record.attempts[0].model={resolved:'local-net/test/qwen2.5:7b'};
  record.lanes=[{id:'verifier',model:'meterless-proxy/deepseek-v4-flash',races:false}];
  assert.equal(verifiedJourney(record).steps[0],'Ask one question tomorrow.');
  record.lanes[0].model='local-net/test/qwen2.5:7b';assert.throws(()=>verifiedJourney(record));
});

test('cloud fleet uses separate DeepSeek generation and verification models', async()=>{
  let saved;
  const flash={id:'meterless-proxy/deepseek-v4-flash',provider:'meterless-proxy',family:'deepseek',kind:'cloud'};
  const rt={MODELS:[flash],findModel:id=>{const model=rt.MODELS.find(row=>row.id===id);return model?.aliasOf?rt.MODELS.find(row=>row.id===model.aliasOf)||model:model||null;},
    fleets:{save:async value=>(saved=value),activate:async()=>({ok:true})},liveLanes:()=>saved.lanes};
  const connection=await connectDeepSeek(rt,'deepseek-v4-pro','deepseek-v4-flash');
  assert.equal(connection.generator,'meterless-proxy/deepseek-v4-pro');
  assert.equal(connection.grader,'meterless-proxy/deepseek-v4-flash');
  assert.notEqual(connection.generator,connection.grader);
  assert.equal(rt.findModel(connection.generator).name,'DeepSeek V4 Pro (official API)');
  assert.equal(rt.findModel('deepseek-v4-pro').id,connection.generator);
  assert.equal(rt.findModel(connection.generator).costOutM,3.96);
  assert.equal(saved.lanes.find(lane=>lane.id==='verifier').races,false);
  await assert.rejects(()=>connectDeepSeek(rt,'deepseek-v4-flash','deepseek-v4-flash'));
});
