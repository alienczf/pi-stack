import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const packageDir = resolve(process.argv[2]);
const require = createRequire(resolve(packageDir, 'package.json'));
const { createJiti } = require('jiti');
const jiti = createJiti(import.meta.url);
const { discoverAgents } = await jiti.import(resolve(packageDir, 'src/agents/agents.ts'));
const { agents } = discoverAgents(process.cwd(), 'both');
assert.deepEqual(agents.map(agent => agent.name).sort(), ['poteto-agent']);
const [agent] = agents;
assert.equal(agent.source, 'user');
assert.equal(agent.disabled, false);
assert.deepEqual(agent.tools, ['read', 'grep', 'find', 'ls', 'bash', 'edit', 'write']);
assert.match(agent.systemPrompt, /poteto-mode\/SKILL\.md/);
assert.match(agent.systemPrompt, /Do not spawn children or use supervisor coordination/);
console.log('check-agent-discovery ok: only poteto-agent; no children launched');
