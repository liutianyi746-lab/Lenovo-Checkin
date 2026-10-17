import test from 'node:test';
import assert from 'node:assert/strict';
import { constants, createDecipheriv, createHash, createPublicKey, generateKeyPairSync, privateDecrypt, publicEncrypt } from 'node:crypto';
import { createClient, makeSn, makeToken, runCheckin, signedStatus, validateConfig } from './checkin.mjs';

const config = {
  authorization:'Lenovo fixture-session', imei:'fixture_client_123', uid:'12345',
  flags:{ enE:false, enR:false, enF:false }
};
const statusCall = ['GET','/signin/v2/assetsAndStatus',{ source:'0' }];
const signCall = ['POST','/signin/v2/add',{ uid:config.uid, source:'0', imei:config.imei }];

// Decode the documented wire structure rather than reproduce its generator.
function assertSn(value, seconds, bootstrap) {
  const body = value.slice(0,72);
  assert.equal(body.length,72);
  assert.equal(value.slice(72),[...Buffer.from(body)].reduce((sum,b) => sum+b,0).toString(16));
  let salt = '', unique = '';
  for (let i=0;i<64;i+=4) {
    salt += body[i+1];
    unique += body[i] + body.slice(i+2,i+4);
  }
  unique += body.slice(64);
  assert.equal(salt,String(seconds).padStart(16,'0'));
  assert.equal(unique.length,56);
  const insert = bootstrap ? 1 : 3;
  let text = '';
  for (let i=0;i<56;i+=7) {
    const group = unique.slice(i,i+7);
    assert.match(group[insert],/^\d$/);
    text += group.slice(0,insert) + group.slice(insert+1);
  }
  assert.equal(text.length,48);
  if (bootstrap) assert.match(text,/^[a-zA-Z]+$/);
  else {
    const alphabet = 'S<e$O|Yy0Z_Eq+dIFl}L6o^Q3X)WwUsmR@=vV9~PK1T#5hM{a]DG4[Ju)/7tNg,b?H!cA&iB8.p*C2>oI(0f;-n$zLq';
    assert([...text].every(c => alphabet.includes(c)));
  }
}

function assertToken(value, ms) {
  assert.match(value,/^[0-9a-f]{112}$/);
  assert.equal(BigInt('0x'+value.slice(64,80)),BigInt(ms));
  const timestamp = Buffer.alloc(8);
  timestamp.writeBigInt64LE(BigInt(ms));
  const entropy = Buffer.from(value.slice(80),'hex');
  assert.equal(entropy.length,16);
  assert.equal(value.slice(0,64),createHash('sha256').update(timestamp).update(entropy).digest('hex'));
}

function scriptedClient(results) {
  const calls = [];
  return {
    calls,
    client:async (...args) => {
      const index = calls.push(args)-1;
      assert(index < results.length,'Unexpected retry or extra request');
      const result = results[index];
      if (result instanceof Error) throw result;
      return result;
    }
  };
}

test('bootstrap and encrypted-body SN retain timestamp, interleave and checksum',() => {
  const seconds = 1700000000;
  assertSn(makeSn(seconds,true),seconds,true);
  assertSn(makeSn(seconds,false),seconds,false);
});

test('temporal token binds its encoded timestamp and entropy to SHA-256',() => {
  const ms = 1700000000123;
  assertToken(makeToken(ms),ms);
});

test('only explicit booleans and true/false strings are accepted as status',() => {
  for (const value of [true,'true']) assert.equal(signedStatus({ isSign:value }),true);
  for (const value of [false,'false']) assert.equal(signedStatus({ isSign:value }),false);
  for (const value of [undefined,null,'',0,1,'0','1','TRUE','false ']) {
    assert.throws(() => signedStatus({ isSign:value }),/明确的签到状态/);
  }
  assert.throws(() => signedStatus(null),/明确的签到状态/);
});

test('invalid credentials are rejected before a client can send requests',() => {
  validateConfig(config);
  assert.throws(() => validateConfig({ ...config, authorization:'Lenovo value\r\nInjected: yes' }));
  assert.throws(() => validateConfig({ ...config, uid:'0' }));
  assert.throws(() => validateConfig({ ...config, flags:{ ...config.flags,enE:'false' } }));
});

test('unknown status never submits a check-in',async () => {
  const stub = scriptedClient([{}]);
  await assert.rejects(runCheckin(config,stub.client),/明确的签到状态/);
  assert.deepEqual(stub.calls,[statusCall]);
});

test('already signed string never submits a check-in',async () => {
  const stub = scriptedClient([{ isSign:'true',continueCount:'54' }]);
  assert.deepEqual(await runCheckin(config,stub.client),{ result:'already_signed',continueCount:'54' });
  assert.deepEqual(stub.calls,[statusCall]);
});

test('status-only mode observes false string without submitting',async () => {
  const stub = scriptedClient([{ isSign:'false',continueCount:'0' }]);
  assert.deepEqual(await runCheckin(config,stub.client,true),{ result:'not_signed',continueCount:'0' });
  assert.deepEqual(stub.calls,[statusCall]);
});

test('unsigned string submits once and requires a fresh positive confirmation',async () => {
  const stub = scriptedClient([{ isSign:'false' },{}, { isSign:'true',continueCount:'55' }]);
  assert.deepEqual(await runCheckin(config,stub.client),{ result:'signed',continueCount:'55' });
  assert.deepEqual(stub.calls,[statusCall,signCall,statusCall]);
});

for (const [name,results,expectedCalls] of [
  ['initial query fails',[new Error('query failed')],[statusCall]],
  ['submission fails',[{ isSign:'false' },new Error('submission failed')],[statusCall,signCall]],
  ['confirmation query fails',[{ isSign:'false' },{},new Error('confirmation failed')],[statusCall,signCall,statusCall]],
  ['confirmation remains false',[{ isSign:'false' },{},{ isSign:'false' }],[statusCall,signCall,statusCall]],
  ['confirmation is ambiguous',[{ isSign:'false' },{},{}],[statusCall,signCall,statusCall]]
]) {
  test(`${name}: failure is reported without retry`,async () => {
    const stub = scriptedClient(results);
    await assert.rejects(runCheckin(config,stub.client));
    assert.deepEqual(stub.calls,expectedCalls);
  });
}

test('offline server verifies RSA bootstrap, AES GET/POST and confirmation end to end',async () => {
  const server = generateKeyPairSync('rsa',{ modulusLength:2048 });
  const aesKey = Buffer.alloc(32,0x31), iv = Buffer.alloc(16,0x42);
  const version = 'fixture.1';
  let bootstrapSn, signed = false, enNumber;
  const events = [];
  const response = res => ({ ok:true,status:200,text:async () => JSON.stringify({ status:0,res }) });

  const mockFetch = async (input,options) => {
    const url = new URL(input), headers = new Headers(options.headers);
    const method = options.method ?? 'GET';
    assert.equal(url.origin,'https://api.club.lenovo.cn');
    assert.equal(options.redirect,'error');
    assert.equal(headers.get('Authorization'),config.authorization);
    assert.equal(headers.get('X-Lenovo-APPID'),'1');
    assert.equal(headers.get('unique'),config.imei);
    assert.deepEqual(JSON.parse(Buffer.from(headers.get('BaseInfo'),'base64').toString('utf8')),{ imei:config.imei,app_version:'7.4.4' });
    events.push([method,url.pathname]);

    if (url.pathname === '/mapi/v2/pre/public') {
      assert.equal(method,'GET');
      assert.equal(options.body,undefined);
      assert.deepEqual([...url.searchParams.keys()],['sn']);
      bootstrapSn = url.searchParams.get('sn');
      const body = bootstrapSn.slice(0,72);
      const seconds = Number(Array.from({ length:16 },(_,i) => body[4*i+1]).join(''));
      assertSn(bootstrapSn,seconds,true);
      return response(server.publicKey.export({ type:'spki',format:'der' }).toString('base64'));
    }
    if (url.pathname === '/mapi/v2/pre/secret') {
      assert.equal(method,'POST');
      assert.match(headers.get('Content-Type'),/^application\/x-www-form-urlencoded; charset=UTF-8$/i);
      const form = new URLSearchParams(options.body);
      assert.deepEqual([...form.keys()].sort(),['appid','pubKey','sn']);
      assert.equal(form.get('sn'),bootstrapSn);
      assert.equal(form.get('appid'),'1');
      const encrypted = Buffer.from(form.get('pubKey'),'base64');
      assert.equal(encrypted.length%256,0);
      const blocks = [];
      for (let i=0;i<encrypted.length;i+=256) {
        const block = privateDecrypt({ key:server.privateKey,padding:constants.RSA_PKCS1_PADDING },encrypted.subarray(i,i+256));
        assert(block.length > 0 && block.length <= 117,'Client SPKI must use 117-byte RSA chunks');
        if (i+256 < encrypted.length) assert.equal(block.length,117);
        blocks.push(block);
      }
      assert.equal(blocks.length,3);
      const clientDer = Buffer.concat(blocks);
      const clientKey = createPublicKey({ key:clientDer,type:'spki',format:'der' });
      assert.equal(clientKey.asymmetricKeyDetails.modulusLength,2048);
      assert.deepEqual(clientKey.export({ type:'spki',format:'der' }),clientDer);
      const wrap = bytes => publicEncrypt({ key:clientKey,padding:constants.RSA_PKCS1_PADDING },Buffer.from(bytes.toString('base64'),'utf8')).toString('base64');
      return response({ pkey:wrap(aesKey),iv:wrap(iv),sversion:version });
    }

    assert.equal(headers.get('sversion'),version);
    const encrypted = method === 'GET' ? url.searchParams.get('s') : options.body;
    assert.match(encrypted,/^(?:[0-9a-f]{32})+$/);
    const decipher = createDecipheriv('aes-256-cbc',aesKey,iv);
    const payload = JSON.parse(Buffer.concat([decipher.update(Buffer.from(encrypted,'hex')),decipher.final()]).toString('utf8'));
    assert.equal(payload.sessionid,config.authorization);
    assert.equal(payload.source,'0');
    assert.match(payload.time,/^\d+$/);
    assertToken(payload.enToken,Number(payload.time));
    assert.equal(payload.enTokenVersion,'1.0.1');
    assert.match(payload.enNumber,/^\d{16}$/);
    if (enNumber === undefined) enNumber = payload.enNumber;
    else assert.equal(payload.enNumber,enNumber);
    assertSn(payload.enSn,Math.floor(Number(payload.time)/1000),false);
    for (const name of ['enE','enR','enF']) assert.equal(payload[name],config.flags[name]);
    if (method === 'GET') {
      assert.equal(url.pathname,'/signin/v2/assetsAndStatus');
      assert.deepEqual([...url.searchParams.keys()],['s']);
      assert.equal(options.body,undefined);
      return response({ isSign:String(signed),continueCount:signed ? '55' : '54' });
    }
    assert.equal(method,'POST');
    assert.equal(url.pathname,'/signin/v2/add');
    assert.equal(url.search,'');
    assert.equal(headers.get('Content-Type'),'text/json');
    assert.equal(payload.uid,config.uid);
    assert.equal(payload.imei,config.imei);
    assert.equal(signed,false,'Duplicate submission');
    signed = true;
    return response({ accepted:true });
  };

  const client = await createClient(config,mockFetch);
  assert.deepEqual(await runCheckin(config,client),{ result:'signed',continueCount:'55' });
  assert.deepEqual(events,[
    ['GET','/mapi/v2/pre/public'], ['POST','/mapi/v2/pre/secret'],
    ['GET','/signin/v2/assetsAndStatus'], ['POST','/signin/v2/add'], ['GET','/signin/v2/assetsAndStatus']
  ]);
});
