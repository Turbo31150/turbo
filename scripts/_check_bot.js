const fs = require('fs');
const code = fs.readFileSync('F:/BUREAU/turbo/canvas/telegram-bot.js', 'utf-8');

const checks = [
  ['normalizeNodes function exists', /function normalizeNodes\(nodes\)/.test(code)],
  ['/status uses normalizeNodes', /case '\/status'[\s\S]{0,400}normalizeNodes/.test(code)],
  ['/health uses normalizeNodes', /case '\/health'[\s\S]{0,400}normalizeNodes/.test(code)],
  ['/ask command exists', /case '\/ask'/.test(code)],
  ['/ping command exists', /case '\/ping'/.test(code)],
  ['/disk command exists', /case '\/disk'/.test(code)],
  ['cmd_disk callback', /cmd_disk/.test(code)],
  ['python3 in domino listing', code.includes("execSync(`python3")],
  ['python3 in domino find', /findResult = execSync\(`python3/.test(code)],
  ['No dead chr(34) code', !code.includes('chr(34)')],
  ['GPU clean parsing (no double MiB)', /usedClean.*\/.*totalClean.*MiB/.test(code)],
  ['Menu has Disque button', code.includes('Disque')],
  ['handleDominos from callback', /cmd_dominos.*handleDominos/.test(code)],
  ['directClusterHealth returns nodeId', /nodeId: node\.id/.test(code)],
  ['CLUSTER_NODES has 4 entries', (code.match(/{ id: '/g) || []).length >= 4],
];

let pass = 0, fail = 0;
for (const [name, ok] of checks) {
  console.log((ok ? 'OK' : 'FAIL') + ' | ' + name);
  ok ? pass++ : fail++;
}
console.log('\n' + pass + '/' + (pass + fail) + ' checks');
if (fail > 0) process.exit(1);
fs.unlinkSync(__filename);
