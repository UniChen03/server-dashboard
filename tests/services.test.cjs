const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function page() {
    class Element {
        constructor(tag) { this.tagName = tag; this.children = []; this.textContent = ''; this.className = ''; }
        appendChild(child) { this.children.push(child); }
        replaceChildren() { this.children = []; this.textContent = ''; }
        classList = { add() {}, remove() {} };
    }
    const elements = new Map();
    const context = vm.createContext({
        URL,
        document: {
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, new Element('div'));
                return elements.get(id);
            },
            createElement(tag) { return new Element(tag); },
        },
        console: { error() {} },
        setInterval() {},
        fetch: () => new Promise(() => {}),
    });
    const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
    vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
    return { context, root: () => context.document.getElementById('services') };
}

test('renders three cards, links, text and stopped status without interpreting HTML', () => {
    const { context, root } = page();
    context.renderServices([
        { name: 'Example App', url: '/example-app/', tag: 'Flask · SQLite', status: 'running' },
        { name: 'Example Admin', url: 'https://admin.example.com/', status: 'exited' },
        { name: 'Example Metrics', description: '<img src=x onerror=alert(1)>', status: 'running' },
    ]);
    assert.equal(root().children.length, 3);
    assert.equal(root().children[0].href, '/example-app/');
    assert.equal(root().children[1].href, 'https://admin.example.com/');
    assert.equal(root().children[1].children.at(-1).textContent, 'Offline (exited)');
    assert.equal(root().children[2].tagName, 'div');
    assert.equal(root().children[2].children[1].textContent, '<img src=x onerror=alert(1)>');
    assert.equal(root().children[0].children.at(-1).textContent, 'Online');
});

test('unsafe links remain non-clickable', () => {
    const { context, root } = page();
    for (const url of ['javascript:alert(1)', '//evil.test', '/\\evil.test', 'data:text/html,x', 'https://user:pass@example.com', '/\n/evil']) {
        context.renderServices([{ name: 'Example', url, status: 'running' }]);
        assert.equal(root().children[0].tagName, 'div');
    }
});

test('refresh removes old cards; empty and Docker unavailable states are distinct', () => {
    const { context, root } = page();
    context.renderServices([{ name: 'Old service', status: 'running' }]);
    context.renderServices([]);
    assert.equal(root().children.length, 0);
    assert.equal(root().textContent, 'No dashboard services enabled');
    context.renderServices(null);
    assert.equal(root().textContent, 'Service status unavailable');
    context.renderServices([{ name: 'New service', status: 'running' }]);
    assert.equal(root().children.length, 1);
    assert.equal(root().children[0].children[0].textContent, 'New service');
});

test('fetch failures clear stale online cards and subsequent polls recover', async () => {
    const { context, root } = page();
    context.renderServices([{ name: 'Old', status: 'running' }]);
    context.fetch = async () => { throw new Error('offline'); };
    await context.updateStatus();
    assert.equal(root().children.length, 0);
    assert.equal(root().textContent, 'Service status unavailable');
    context.fetch = async () => ({ ok: false, status: 503 });
    await context.updateStatus();
    assert.equal(root().textContent, 'Service status unavailable');
    context.fetch = async () => ({ ok: true, json: async () => ({
        docker_services: [{ name: 'Recovered', status: 'running' }],
        docker_running: 1, cpu_percent: 0, memory_used: 1, memory_total: 2,
        system_disk_used: 1, system_disk_total: 2, data_disk_mounted: false,
        cpu_temperature: null, nvme_temperature: null, uptime_seconds: 60,
    }) });
    await context.updateStatus();
    assert.equal(root().children[0].children[0].textContent, 'Recovered');
});
