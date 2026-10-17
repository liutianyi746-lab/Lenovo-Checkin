import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

const config = {
  authorization:'Lenovo FAKE_TOKEN_DO_NOT_PRINT', imei:'fake-device', uid:'12345',
  flags:{ enE:false, enR:false, enF:false }
};

function fixture(t) {
  const dir = mkdtempSync(join(tmpdir(),'lenovo-config-test-'));
  t.after(() => rmSync(dir,{ recursive:true, force:true }));
  for (const file of ['configure.mjs','checkin.mjs']) copyFileSync(new URL(file,import.meta.url),join(dir,file));
  return dir;
}

function run(dir) {
  return spawnSync(process.execPath,[join(dir,'configure.mjs')],{ encoding:'utf8', windowsHide:true });
}

test('valid BOM config imports using CurrentUser DPAPI without printing credentials',{ skip:process.platform !== 'win32' },t => {
  const dir = fixture(t);
  writeFileSync(join(dir,'credentials.dpapi'),'old-encrypted-credentials');
  writeFileSync(join(dir,'credentials.local.json'),'\ufeff' + JSON.stringify(config));
  const result = run(dir);
  assert.equal(result.status,0,result.stderr);
  assert(!result.stdout.includes(config.authorization));
  assert(!result.stderr.includes(config.authorization));
  const encrypted = readFileSync(join(dir,'credentials.dpapi'));
  const command = 'Add-Type -AssemblyName System.Security; $b=[Convert]::FromBase64String([Console]::In.ReadToEnd()); $p=[Security.Cryptography.ProtectedData]::Unprotect($b,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser); [Console]::Write([Convert]::ToBase64String($p))';
  const plain = execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',command],{
    input:encrypted.toString('base64'), encoding:'utf8', windowsHide:true, stdio:['pipe','pipe','pipe']
  });
  assert.deepEqual(JSON.parse(Buffer.from(plain,'base64').toString('utf8')),config);
});

for (const [name,input] of [
  ['missing config',undefined],
  ['invalid config',JSON.stringify({ ...config, uid:'invalid' })],
  ['malformed config','{"authorization":"' + config.authorization + '",oops']
]) {
  test(`${name} does not overwrite credentials or reveal token`,t => {
    const dir = fixture(t);
    const original = Buffer.from('existing-encrypted-credentials');
    writeFileSync(join(dir,'credentials.dpapi'),original);
    if (input !== undefined) writeFileSync(join(dir,'credentials.local.json'),input);
    const result = run(dir);
    assert.notEqual(result.status,0);
    assert.deepEqual(readFileSync(join(dir,'credentials.dpapi')),original);
    assert(!result.stdout.includes('FAKE_TOKEN_DO_NOT_PRINT'));
    assert(!result.stderr.includes('FAKE_TOKEN_DO_NOT_PRINT'));
    assert.match(result.stderr,/导入失败/);
  });
}
