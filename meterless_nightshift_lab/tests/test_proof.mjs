import {test} from 'node:test';
import assert from 'node:assert/strict';
import {assessRun} from '../proof.js';

test('a timeout cannot be promoted to verified even when a score exists',()=>{
  const r={job:{winner_seq:1},attempts:[{seq:1,text:'answer'}],receipt:{receipt_id:'actual'},events:[{t:'verify',verdict:'supported',timed_out:true,scores:[{score:.9}]}]};
  assert.equal(assessRun(r).usableVerifiedAnswer,false);
});

test('the latest actual verifier event controls the displayed verdict',()=>{
  const r={job:{winner_seq:1},attempts:[{seq:1,text:'answer'}],receipt:{receipt_id:'actual'},events:[{t:'verify',verdict:'supported',scores:[{score:.9}]},{t:'verify',verdict:null}]};
  assert.equal(assessRun(r).usableVerifiedAnswer,false);
});
