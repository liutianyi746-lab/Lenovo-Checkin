import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { validateConfig } from './checkin.mjs';

let temporary;
try {
  if (process.platform !== 'win32') throw new Error();
  const config = JSON.parse(readFileSync(new URL('./credentials.local.json',import.meta.url),'utf8').replace(/^\ufeff/,''));
  validateConfig(config);
  const command = '$ErrorActionPreference="Stop"; Add-Type -AssemblyName System.Security; [Console]::InputEncoding=[Text.UTF8Encoding]::new($false); $p=[Text.Encoding]::UTF8.GetBytes([Console]::In.ReadToEnd()); $b=[Security.Cryptography.ProtectedData]::Protect($p,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser); [Console]::Write([Convert]::ToBase64String($b))';
  const encrypted = execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',command],{
    input:JSON.stringify(config), encoding:'utf8', windowsHide:true, stdio:['pipe','pipe','pipe']
  }).trim();
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(encrypted) || encrypted.length % 4 !== 0) throw new Error();
  temporary = fileURLToPath(new URL(`./.credentials.${randomUUID()}.tmp`,import.meta.url));
  writeFileSync(temporary,Buffer.from(encrypted,'base64'),{ flag:'wx', mode:0o600 });
  renameSync(temporary,fileURLToPath(new URL('./credentials.dpapi',import.meta.url)));
  console.log('配置导入成功，已使用当前 Windows 用户加密。请删除 credentials.local.json 明文文件。');
} catch {
  console.error('导入失败：请在 Windows 中检查 credentials.local.json 的格式和必填字段，并确认目录可写。');
  process.exitCode = 1;
} finally {
  if (temporary) {
    try { rmSync(temporary,{ force:true }); } catch {}
  }
}
