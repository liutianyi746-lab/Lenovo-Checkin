import assert from 'node:assert/strict';
import { constants, createCipheriv, createHash, createPublicKey, generateKeyPairSync, privateDecrypt, publicEncrypt, randomBytes, randomInt } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const HOST = 'https://api.club.lenovo.cn';
const LETTERS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
const SN_CHARS = 'S<e$O|Yy0Z_Eq+dIFl}L6o^Q3X)WwUsmR@=vV9~PK1T#5hM{a]DG4[Ju)/7tNg,b?H!cA&iB8.p*C2>oI(0f;-n$zLq';
const digits = n => Array.from({ length:n }, () => String(randomInt(10))).join('');

export function makeSn(seconds, bootstrap = false) {
  const number = digits(8);
  const chars = bootstrap ? LETTERS : SN_CHARS;
  const text = Array.from({ length:48 }, () => chars[randomInt(chars.length)]).join('');
  const insert = bootstrap ? 1 : 3;
  const unique = Array.from({ length:8 }, (_,j) => text.slice(6*j,6*j+insert) + number[j] + text.slice(6*j+insert,6*j+6)).join('');
  const salt = String(seconds).padStart(16,'0');
  const middle = Array.from({ length:16 }, (_,j) => unique[3*j] + salt[j] + unique.slice(3*j+1,3*j+3)).join('') + unique.slice(48);
  return middle + [...Buffer.from(middle)].reduce((sum,n) => sum+n,0).toString(16);
}

export function makeToken(ms) {
  const stamp = Buffer.alloc(8);
  stamp.writeBigInt64LE(BigInt(ms));
  const entropy = randomBytes(16);
  return createHash('sha256').update(stamp).update(entropy).digest('hex') + BigInt(ms).toString(16).padStart(16,'0') + entropy.toString('hex');
}

export function validateConfig(config) {
  assert(typeof config.authorization === 'string' && /^Lenovo [^\r\n]{1,8192}$/.test(config.authorization), '登录态格式不正确');
  assert(typeof config.imei === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(config.imei), '客户端标识不正确');
  assert(typeof config.uid === 'string' && /^[1-9][0-9]{0,23}$/.test(config.uid), '账号 UID 不正确');
  for (const name of ['enE','enR','enF']) assert(typeof config.flags?.[name] === 'boolean', '缺少已验证的 App 环境字段');
}

export async function createClient(config, fetchImpl = fetch) {
  validateConfig(config);
  const headers = {
    'X-Lenovo-APPID':'1', versionCode:'1000163', Authorization:config.authorization,
    unique:config.imei, BaseInfo:Buffer.from(JSON.stringify({ imei:config.imei, app_version:'7.4.4' })).toString('base64'),
    'User-Agent':'Apache-HttpClient/UNAVAILABLE (java 1.4)', 'Accept-Encoding':'identity'
  };
  async function request(path, options = {}) {
    const response = await fetchImpl(HOST + path, {
      ...options, headers:{ ...headers, ...options.headers }, redirect:'error', signal:AbortSignal.timeout(25000)
    });
    const text = await response.text();
    assert(text.length <= 1024*1024, '接口响应过大');
    let data;
    try { data = JSON.parse(text); } catch { throw new Error(`接口返回非 JSON：HTTP ${response.status}`); }
    if (!response.ok || data?.status !== 0 || data.res == null) {
      const code = String(data?.res?.error_code ?? 'unknown').replace(/[^0-9a-z_-]/gi,'').slice(0,24);
      throw new Error(`接口未成功：HTTP ${response.status}，错误码 ${code}。登录态可能需要更新。`);
    }
    return data.res;
  }

  const sn = makeSn(Math.floor(Date.now()/1000),true);
  const serverPublic = await request('/mapi/v2/pre/public?' + new URLSearchParams({ sn }));
  assert(typeof serverPublic === 'string' && serverPublic.length < 16384, '服务端公钥格式不正确');
  const serverKey = createPublicKey({ key:Buffer.from(serverPublic,'base64'), type:'spki', format:'der' });
  const { privateKey, publicKey } = generateKeyPairSync('rsa',{ modulusLength:2048 });
  const publicDer = publicKey.export({ type:'spki', format:'der' });
  const chunks = [];
  for (let i=0;i<publicDer.length;i+=117) chunks.push(publicEncrypt({ key:serverKey, padding:constants.RSA_PKCS1_PADDING }, publicDer.subarray(i,i+117)));
  const pre = await request('/mapi/v2/pre/secret', {
    method:'POST', headers:{ 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8' },
    body:new URLSearchParams({ sn, appid:'1', pubKey:Buffer.concat(chunks).toString('base64') })
  });
  function unwrap(value) {
    assert(typeof value === 'string' && value.length < 16384, '握手密钥格式不正确');
    const raw = Buffer.from(value,'base64');
    assert(raw.length > 0 && raw.length % 256 === 0, '握手密钥长度不正确');
    const blocks = [];
    for (let i=0;i<raw.length;i+=256) blocks.push(privateDecrypt({ key:privateKey, padding:constants.RSA_PKCS1_PADDING },raw.subarray(i,i+256)));
    return Buffer.from(Buffer.concat(blocks).toString('utf8').trim(),'base64');
  }
  const key = unwrap(pre.pkey);
  const iv = unwrap(pre.iv);
  assert([16,24,32].includes(key.length) && iv.length === 16, 'AES 密钥长度不正确');
  assert(typeof pre.sversion === 'string' && /^[a-zA-Z0-9._-]{1,256}$/.test(pre.sversion), '握手版本格式不正确');
  const enNumber = digits(16);

  return async (method, path, params) => {
    const now = Date.now();
    const payload = {
      ...params, sessionid:config.authorization, time:String(now), enToken:makeToken(now),
      enTokenVersion:'1.0.1', enNumber, ...config.flags, enSn:makeSn(Math.floor(now/1000))
    };
    const cipher = createCipheriv(`aes-${key.length*8}-cbc`,key,iv);
    const encrypted = Buffer.concat([cipher.update(JSON.stringify(payload),'utf8'),cipher.final()]).toString('hex');
    return method === 'GET'
      ? request(path + '?' + new URLSearchParams({ s:encrypted }),{ headers:{ sversion:pre.sversion } })
      : request(path,{ method:'POST', headers:{ sversion:pre.sversion, 'Content-Type':'text/json' }, body:encrypted });
  };
}

export function signedStatus(response) {
  if (response?.isSign === true || response?.isSign === 'true') return true;
  if (response?.isSign === false || response?.isSign === 'false') return false;
  throw new Error('服务器没有返回明确的签到状态，已停止操作');
}

export async function runCheckin(config, client, statusOnly = false) {
  const status = await client('GET','/signin/v2/assetsAndStatus',{ source:'0' });
  if (signedStatus(status)) return { result:'already_signed', continueCount:status.continueCount };
  if (statusOnly) return { result:'not_signed', continueCount:status.continueCount };
  // shortcut: 登录态从当前 App 导入；失效时需重新登录并更新，尚未实现独立登录流程。
  await client('POST','/signin/v2/add',{ uid:config.uid, source:'0', imei:config.imei });
  const after = await client('GET','/signin/v2/assetsAndStatus',{ source:'0' });
  if (!signedStatus(after)) throw new Error('已提交签到，但服务器尚未确认成功；请稍后查询状态');
  return { result:'signed', continueCount:after.continueCount };
}

function loadConfig() {
  const path = fileURLToPath(new URL('./credentials.dpapi',import.meta.url));
  const command = 'Add-Type -AssemblyName System.Security; $b=[IO.File]::ReadAllBytes($env:LENOVO_CONFIG_FILE); $p=[Security.Cryptography.ProtectedData]::Unprotect($b,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser); [Console]::Write([Text.Encoding]::UTF8.GetString($p))';
  try {
    return JSON.parse(execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',command],{
      env:{ ...process.env, LENOVO_CONFIG_FILE:path }, encoding:'utf8', windowsHide:true, stdio:['ignore','pipe','pipe']
    }));
  } catch { throw new Error('无法读取本机登录态：请使用原 Windows 用户运行，并检查 credentials.dpapi 文件'); }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  try {
    assert(process.argv.slice(2).every(arg => arg === '--status'),'仅支持 --status（只查询）或不带参数（签到）');
    const config = loadConfig();
    const result = await runCheckin(config,await createClient(config),process.argv.includes('--status'));
    const message = { already_signed:'今日已签到', signed:'签到成功', not_signed:'今日尚未签到' }[result.result];
    console.log(`${message}；连续签到 ${result.continueCount ?? '未知'} 天。`);
  } catch (error) {
    console.error(`运行失败：${error instanceof assert.AssertionError ? error.message : error.message || '未知错误'}`);
    process.exitCode = 1;
  }
}
