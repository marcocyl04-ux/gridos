// GridOS DevTools - AI-Friendly Development Interface
// This interface exposes the node graph system for easy manipulation

const API_BASE = window.location.origin;

// State management
const state = {
    activePanel: 'graph',
    nodes: [],
    connections: [],
    selectedNode: null,
    apiEndpoints: [],
    selectedEndpoint: null,
    templates: [],
    selectedTemplate: null,
    systemHealth: null
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initGraphPanel();
    initApiPanel();
    initPlaygroundPanel();
    initBuilderPanel();
    initHealthPanel();
    loadSystemStatus();
});

// Navigation
function initNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn[data-panel]');
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const panel = btn.dataset.panel;
            switchPanel(panel);
        });
    });
}

function switchPanel(panelName) {
    // Update nav
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.nav-btn[data-panel="${panelName}"]`).classList.add('active');
    
    // Update panel
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`${panelName}-panel`).classList.add('active');
    
    // Update toolbar title
    const titles = {
        'graph': 'Node Graph Visualizer',
        'api': 'API Explorer',
        'playground': 'Intent Playground',
        'builder': 'Template Builder',
        'health': 'System Health'
    };
    document.querySelector('.toolbar-title').textContent = titles[panelName];
    
    state.activePanel = panelName;
    
    // Refresh data if needed
    if (panelName === 'api') loadApiEndpoints();
    if (panelName === 'health') loadSystemHealth();
}

// ============ NODE GRAPH PANEL ============

function initGraphPanel() {
    const canvas = document.getElementById('graph-canvas');
    const svg = document.getElementById('graph-svg');
    
    // Sample graph for demonstration
    state.nodes = [
        { id: 'n1', type: 'QUERY', x: 50, y: 100, label: 'Get Revenue' },
        { id: 'n2', type: 'FORMULA', x: 250, y: 100, label: 'Calculate Growth' },
        { id: 'n3', type: 'CELL_WRITE', x: 450, y: 100, label: 'Write Result' },
        { id: 'n4', type: 'CONDITIONAL', x: 250, y: 250, label: 'Check > 0' }
    ];
    
    state.connections = [
        { from: 'n1', to: 'n2', label: 'revenue' },
        { from: 'n2', to: 'n3', label: 'result' },
        { from: 'n2', to: 'n4', label: 'growth' }
    ];
    
    renderGraph();
    initGraphDragDrop();
    
    // Node palette drag
    document.querySelectorAll('.palette-item').forEach(item => {
        item.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('nodeType', item.dataset.type);
        });
        item.draggable = true;
    });
    
    // Execute graph button
    document.getElementById('execute-graph-btn').addEventListener('click', executeGraph);
}

function renderGraph() {
    const svg = document.getElementById('graph-svg');
    svg.innerHTML = '';
    
    // Render connections
    state.connections.forEach((conn, idx) => {
        const fromNode = state.nodes.find(n => n.id === conn.from);
        const toNode = state.nodes.find(n => n.id === conn.to);
        
        if (fromNode && toNode) {
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const d = `M ${fromNode.x + 90} ${fromNode.y + 25} 
                       C ${fromNode.x + 140} ${fromNode.y + 25},
                         ${toNode.x - 50} ${toNode.y + 25},
                         ${toNode.x} ${toNode.y + 25}`;
            path.setAttribute('d', d);
            path.setAttribute('class', 'connection');
            path.setAttribute('id', `conn-${idx}`);
            svg.appendChild(path);
        }
    });
    
    // Render nodes
    state.nodes.forEach(node => {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'node');
        g.setAttribute('transform', `translate(${node.x}, ${node.y})`);
        g.setAttribute('data-id', node.id);
        
        const colors = {
            'CELL_WRITE': '#238636',
            'RANGE_WRITE': '#238636',
            'FORMULA': '#f0883e',
            'CONDITIONAL': '#a371f7',
            'AGGREGATE': '#f0883e',
            'QUERY': '#58a6ff',
            'GROUP': '#8b949e'
        };
        
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', 90);
        rect.setAttribute('height', 50);
        rect.setAttribute('class', 'node-rect');
        rect.setAttribute('fill', colors[node.type] || '#8b949e');
        rect.setAttribute('stroke', colors[node.type] || '#8b949e');
        
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', 45);
        text.setAttribute('y', 22);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('class', 'node-text');
        text.textContent = node.label;
        
        const typeText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        typeText.setAttribute('x', 45);
        typeText.setAttribute('y', 38);
        typeText.setAttribute('text-anchor', 'middle');
        typeText.setAttribute('class', 'node-type-text');
        typeText.textContent = node.type;
        
        g.appendChild(rect);
        g.appendChild(text);
        g.appendChild(typeText);
        svg.appendChild(g);
    });
}

function initGraphDragDrop() {
    let draggedNode = null;
    let dragOffset = { x: 0, y: 0 };
    
    const svg = document.getElementById('graph-svg');
    
    svg.addEventListener('mousedown', (e) => {
        const nodeEl = e.target.closest('.node');
        if (nodeEl) {
            draggedNode = state.nodes.find(n => n.id === nodeEl.dataset.id);
            const rect = svg.getBoundingClientRect();
            dragOffset.x = e.clientX - rect.left - draggedNode.x;
            dragOffset.y = e.clientY - rect.top - draggedNode.y;
            nodeEl.classList.add('dragging');
        }
    });
    
    svg.addEventListener('mousemove', (e) => {
        if (draggedNode) {
            const rect = svg.getBoundingClientRect();
            draggedNode.x = e.clientX - rect.left - dragOffset.x;
            draggedNode.y = e.clientY - rect.top - dragOffset.y;
            renderGraph();
        }
    });
    
    svg.addEventListener('mouseup', () => {
        if (draggedNode) {
            document.querySelector('.node.dragging')?.classList.remove('dragging');
            draggedNode = null;
        }
    });
}

async function executeGraph() {
    const btn = document.getElementById('execute-graph-btn');
    btn.textContent = 'Executing...';
    btn.disabled = true;
    
    try {
        // Convert visual graph to node graph JSON
        const graphData = {
            nodes: state.nodes.map(n => ({
                id: n.id,
                node_type: n.type,
                interface: {
                    inputs: {},
                    outputs: {}
                },
                inputs: {},
                outputs: {}
            })),
            connections: state.connections
        };
        
        const response = await fetch(`${API_BASE}/agent/execute-graph`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(graphData)
        });
        
        const result = await response.json();
        showToast(`Graph executed: ${result.status || 'success'}`);
        
        // Show result in properties panel
        document.getElementById('node-properties').innerHTML = `
            <h4>Execution Result</h4>
            <pre>${JSON.stringify(result, null, 2)}</pre>
        `;
        
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    } finally {
        btn.textContent = 'Execute Graph';
        btn.disabled = false;
    }
}

// ============ API EXPLORER PANEL ============

async function loadApiEndpoints() {
    try {
        // Fetch from OpenAPI spec or introspect
        const response = await fetch(`${API_BASE}/openapi.json`);
        if (response.ok) {
            const spec = await response.json();
            state.apiEndpoints = parseOpenApi(spec);
        } else {
            // Fallback: use hardcoded endpoints we know exist
            state.apiEndpoints = getKnownEndpoints();
        }
        renderApiList();
    } catch (err) {
        state.apiEndpoints = getKnownEndpoints();
        renderApiList();
    }
}

function getKnownEndpoints() {
    return [
        { method: 'POST', path: '/agent/chat', description: 'Send message to agent' },
        { method: 'POST', path: '/agent/execute-graph', description: 'Execute node graph' },
        { method: 'POST', path: '/agent/write', description: 'Write to grid via agent' },
        { method: 'POST', path: '/agent/write/graph', description: 'Write via node graph' },
        { method: 'POST', path: '/grid/cell', description: 'Write single cell' },
        { method: 'POST', path: '/grid/range', description: 'Write cell range' },
        { method: 'POST', path: '/grid/clear', description: 'Clear grid' },
        { method: 'POST', path: '/formula/evaluate', description: 'Evaluate formula' },
        { method: 'POST', path: '/import/file', description: 'Import file' },
        { method: 'GET', path: '/templates/available', description: 'List templates' },
        { method: 'POST', path: '/templates/apply/{id}', description: 'Apply template' },
        { method: 'GET', path: '/healthz', description: 'Health check' },
        { method: 'GET', path: '/auth/whoami', description: 'Current user info' }
    ];
}

function renderApiList() {
    const list = document.getElementById('api-list');
    list.innerHTML = '';
    
    state.apiEndpoints.forEach((endpoint, idx) => {
        const item = document.createElement('div');
        item.className = 'api-item';
        item.innerHTML = `
            <span class="method ${endpoint.method.toLowerCase()}">${endpoint.method}</span>
            <span class="path">${endpoint.path}</span>
        `;
        item.addEventListener('click', () => selectEndpoint(idx));
        list.appendChild(item);
    });
}

function selectEndpoint(idx) {
    state.selectedEndpoint = state.apiEndpoints[idx];
    
    document.querySelectorAll('.api-item').forEach((el, i) => {
        el.classList.toggle('active', i === idx);
    });
    
    renderApiDetail();
}

function renderApiDetail() {
    const endpoint = state.selectedEndpoint;
    if (!endpoint) return;
    
    document.getElementById('api-detail').innerHTML = `
        <div class="api-detail-section">
            <h4>Endpoint</h4>
            <div class="code-block">
                <pre><span class="key">${endpoint.method}</span> <span class="string">${endpoint.path}</span></pre>
            </div>
            <p style="margin-top: 12px; color: var(--text-secondary); font-size: 13px;">
                ${endpoint.description || 'No description available'}
            </p>
        </div>
        
        <div class="api-detail-section">
            <h4>Test Request</h4>
            <div class="code-block">
                <pre contenteditable="true" id="request-body" style="min-height: 150px; outline: none;">${getExamplePayload(endpoint)}</pre>
            </div>
            <button class="btn btn-primary" onclick="testEndpoint()" style="margin-top: 12px;">
                Send Request
            </button>
        </div>
        
        <div class="api-detail-section" id="response-section" style="display: none;">
            <h4>Response</h4>
            <div class="code-block">
                <pre id="response-body">...</pre>
            </div>
        </div>
    `;
}

function getExamplePayload(endpoint) {
    const examples = {
        '/agent/chat': JSON.stringify({
            workbook_id: "test-workbook",
            agent_id: "default",
            message: "Calculate revenue growth for Q1"
        }, null, 2),
        '/agent/execute-graph': JSON.stringify({
            nodes: [
                { id: "1", node_type: "QUERY", inputs: { range: "A1:A10" } }
            ]
        }, null, 2),
        '/grid/cell': JSON.stringify({
            cell: "A1",
            value: 100
        }, null, 2),
        '/templates/apply/{id}': JSON.stringify({
            variables: { company_name: "Acme Corp" }
        }, null, 2)
    };
    return examples[endpoint.path] || '{}';
}

async function testEndpoint() {
    const endpoint = state.selectedEndpoint;
    const body = document.getElementById('request-body').textContent;
    
    document.getElementById('response-section').style.display = 'block';
    document.getElementById('response-body').textContent = 'Loading...';
    
    try {
        const options = {
            method: endpoint.method,
            headers: { 'Content-Type': 'application/json' }
        };
        
        if (endpoint.method !== 'GET') {
            options.body = body;
        }
        
        const response = await fetch(`${API_BASE}${endpoint.path}`, options);
        const result = await response.json();
        
        document.getElementById('response-body').innerHTML = syntaxHighlight(result);
    } catch (err) {
        document.getElementById('response-body').textContent = `Error: ${err.message}`;
    }
}

// ============ INTENT PLAYGROUND ============

function initPlaygroundPanel() {
    document.getElementById('execute-intent-btn').addEventListener('click', executeIntent);
}

async function executeIntent() {
    const input = document.getElementById('intent-input').value;
    const output = document.getElementById('intent-output');
    
    output.innerHTML = '<div style="color: var(--text-secondary)">Parsing intent...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/agent/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workbook_id: 'playground',
                agent_id: 'default',
                message: input
            })
        });
        
        const result = await response.json();
        
        output.innerHTML = `
            <div style="margin-bottom: 16px;">
                <h4 style="color: var(--accent); margin-bottom: 8px;">Parsed Intent</h4>
                <div class="code-block"><pre>${syntaxHighlight(result)}</pre></div>
            </div>
            ${result.nodes ? `
            <div>
                <h4 style="color: var(--success); margin-bottom: 8px;